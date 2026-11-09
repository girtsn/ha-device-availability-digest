"""Durable grouped availability alerts using Home Assistant's atomic storage.

Replaces the single per-device delay/wait automation. Pending outages,
confirmed outages, digest deadlines and recovery events survive HA restarts.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_STATE_CHANGED
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import area_registry, device_registry, entity_registry
from homeassistant.helpers.event import async_track_time_interval, async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN, DOMAINS, UNHEALTHY_CONNECTION,
    CONF_NOTIFY, CONF_OFFLINE_MINUTES, CONF_WINDOW_MINUTES,
    CONF_EXCLUDED_ENTITIES, CONF_EXCLUDED_DEVICE_ANCHORS,
    CONF_CONNECTIVITY_ENTITIES, CONF_AUTO_EXCLUDE_TVS,
    CONF_EMAIL_SUBJECT_PREFIX, DEFAULT_EMAIL_SUBJECT_PREFIX,
)
from .model import AvailabilityState, format_subject, is_nonphysical_device, parse, utcnow
from .history import DiagnosticHistory
from .diagnostics_api import ws_get_history
from .stale_monitor import StaleSensorMonitor

_LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PANEL_PATH = "device-availability"
ASSET_PATH = "/device_availability_digest"
PANEL_VERSION = json.loads(
    (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
)["version"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register read-only diagnostics and integration-managed panel assets."""
    root = Path(__file__).parent
    await hass.http.async_register_static_paths([
        StaticPathConfig(
            f"{ASSET_PATH}/manifest.json",
            str(root / "manifest.json"),
            cache_headers=False,
        ),
        StaticPathConfig(
            f"{ASSET_PATH}/panel-loader.js",
            str(root / "www" / "panel-loader.js"),
            cache_headers=False,
        ),
        StaticPathConfig(
            f"{ASSET_PATH}/assets/{PANEL_VERSION}/managed-panel.js",
            str(root / "www" / "managed-panel.js"),
            cache_headers=False,
        ),
        StaticPathConfig(
            f"{ASSET_PATH}/assets/{PANEL_VERSION}/availability-date-range-picker.js",
            str(root / "www" / "availability-date-range-picker.js"),
            cache_headers=False,
        ),
    ])
    websocket_api.async_register_command(hass, ws_get_history)
    return True


async def _async_register_diagnostics_panel(hass: HomeAssistant) -> None:
    """Create a one-click dashboard matching other managed integration panels."""
    if frontend.async_panel_exists(hass, PANEL_PATH):
        return
    try:
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_PATH,
            webcomponent_name="availability-diagnostics-loader-panel",
            sidebar_title="Availability",
            sidebar_icon="mdi:lan-check",
            module_url=f"{ASSET_PATH}/panel-loader.js",
            config={"integration_version": PANEL_VERSION},
            require_admin=True,
        )
    except (ValueError, RuntimeError):
        _LOGGER.warning("Could not register Availability diagnostics panel", exc_info=True)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Start the persistent monitor for the single configured instance."""
    options = {**entry.data, **entry.options}
    monitor = AvailabilityDigest(hass, options)
    monitor.history = DiagnosticHistory(hass)
    await monitor.history.load()
    await monitor.load()
    if options.get("stale_monitor_enabled", True):
        monitor.stale = StaleSensorMonitor(
            hass, monitor._send, monitor._subject, monitor.history
        )
        await monitor.stale.load()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = monitor

    @callback
    def on_change(event: Event) -> None:
        hass.async_create_task(monitor.on_change(event))

    @callback
    def on_timer(now: datetime) -> None:
        hass.async_create_task(monitor.on_timer(now))

    entry.async_on_unload(hass.bus.async_listen(EVENT_STATE_CHANGED, on_change))
    entry.async_on_unload(async_track_time_interval(hass, on_timer, timedelta(seconds=30)))
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    if monitor.stale is not None:
        @callback
        def on_stale_tick(_: datetime) -> None:
            hass.async_create_task(monitor.stale.scan())

        @callback
        def on_stale_digest(_: datetime) -> None:
            hass.async_create_task(monitor.stale.scan(send_digest=True))

        entry.async_on_unload(async_track_time_interval(
            hass, on_stale_tick, timedelta(minutes=15)
        ))
        for hour in (8, 20):
            entry.async_on_unload(async_track_time_change(
                hass, on_stale_digest, hour=hour, minute=0, second=0
            ))

    @callback
    def on_registry_changed(_: Event) -> None:
        monitor._representatives.clear()

    entry.async_on_unload(hass.bus.async_listen("entity_registry_updated", on_registry_changed))
    entry.async_on_unload(hass.bus.async_listen("device_registry_updated", on_registry_changed))
    # Reusable read-only household presence sensor. Separate from the
    # notification monitor; it must not issue actions on consumer devices.
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    await _async_register_diagnostics_panel(hass)

    async def start_monitors() -> None:
        await monitor.reconcile()
        if monitor.stale is not None:
            await monitor.stale.scan()

    if hass.state == CoreState.running:
        hass.async_create_task(start_monitors())
    else:
        @callback
        def on_started(_: Event) -> None:
            hass.async_create_task(start_monitors())

        entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, on_started))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload after changes in the UI options flow."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the presence sensor and notification listeners."""
    if not await hass.config_entries.async_unload_platforms(entry, ["sensor"]):
        return False
    monitor = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if monitor:
        monitor.started = False
        if monitor.stale is not None:
            monitor.stale.started = False
    entry.async_unload_callbacks()
    if not hass.data.get(DOMAIN):
        frontend.async_remove_panel(hass, PANEL_PATH, warn_if_unknown=False)
    return True


class AvailabilityDigest:
    def __init__(self, hass: HomeAssistant, options: dict) -> None:
        self.hass = hass
        self.notify_entity = options[CONF_NOTIFY]
        self.subject_prefix = str(options.get(CONF_EMAIL_SUBJECT_PREFIX, DEFAULT_EMAIL_SUBJECT_PREFIX)).strip()
        self.delay = timedelta(minutes=options[CONF_OFFLINE_MINUTES])
        self.window = timedelta(minutes=options[CONF_WINDOW_MINUTES])
        self.excluded_entities = set(options.get(CONF_EXCLUDED_ENTITIES, []))
        self.excluded_device_anchors = set(options.get(CONF_EXCLUDED_DEVICE_ANCHORS, []))
        self.connectivity_entities = set(options.get(CONF_CONNECTIVITY_ENTITIES, []))
        self.auto_exclude_tvs = options.get(CONF_AUTO_EXCLUDE_TVS, True)
        self._representatives: dict[str, str] = {}
        self.store = Store(hass, 1, DOMAIN, private=True, atomic_writes=True)
        self.state = AvailabilityState()
        self.history: DiagnosticHistory | None = None
        self.stale: StaleSensorMonitor | None = None
        self.lock = asyncio.Lock()
        self.started = False

    async def load(self) -> None:
        self.state = AvailabilityState(await self.store.async_load())

    async def save(self) -> None:
        await self.store.async_save(self.state.snapshot())

    async def _record_new_availability_events(self, previous_count: int) -> None:
        """Copy only confirmed OFFLINE/RECOVERED events to diagnostic history."""
        if self.history is None or self.state.batch is None:
            return
        events = self.state.batch.get("events", [])[previous_count:]
        for evt in events:
            await self.history.record(
                "availability_event",
                event=evt.get("kind"),
                entity_id=evt.get("entity_id"),
                name=evt.get("name"),
                area=evt.get("area"),
                scope=evt.get("scope"),
                integration=evt.get("integration"),
                occurred_at=evt.get("at"),
                since=evt.get("since"),
                minutes=evt.get("minutes"),
                failure_reason=evt.get("failure_reason"),
                last_successful_update=evt.get("last_successful_update"),
            )

    def _device_id(self, eid: str) -> str | None:
        entry = entity_registry.async_get(self.hass).async_get(eid)
        return entry.device_id if entry else None

    def _nonphysical_endpoint(self, eid: str) -> bool:
        """Recognize virtual HA services and tado logical heating zones."""
        did = self._device_id(eid)
        device = device_registry.async_get(self.hass).async_get(did) if did else None
        return bool(device and is_nonphysical_device(
            device.entry_type, device.manufacturer, device.model
        ))

    def _prune_nonphysical_incidents(self) -> bool:
        """Retire persisted service/room incidents without recovery messages."""
        ids = set(self.state.pending) | set(self.state.active)
        if self.state.batch:
            ids.update(item["entity_id"] for item in self.state.batch["events"])
        return self.state.discard_entities({
            eid for eid in ids if self._nonphysical_endpoint(eid)
        })

    def _source_integration(self, eid: str) -> str:
        entry = entity_registry.async_get(self.hass).async_get(eid)
        return entry.platform if entry else "unknown"

    def _ignored(self, eid: str, did: str | None) -> bool:
        if not did or eid in self.excluded_entities:
            return True
        if did in {self._device_id(anchor) for anchor in self.excluded_device_anchors}:
            return True
        device = device_registry.async_get(self.hass).async_get(did)
        if not device:
            return False
        if is_nonphysical_device(device.entry_type, device.manufacturer, device.model):
            return True
        if not self.auto_exclude_tvs:
            return False
        description = " ".join(str(x or "") for x in (
            device.name_by_user, device.name, device.manufacturer, device.model
        )).lower()
        has_media_player = any(
            entry.device_id == did and entry.entity_id.startswith("media_player.")
            for entry in entity_registry.async_get(self.hass).entities.values()
        )
        return has_media_player and any(
            word in description for word in (" tv", "television", "webos", "oled", "bravia", "roku")
        )

    def _is_tado_api(self, eid: str, attrs: dict) -> bool:
        return (eid.startswith("binary_sensor.")
                and attrs.get("connectivity_scope") in {"main_api", "settings_api"}
                and attrs.get("tado_home_id") is not None)

    def _is_cloud(self, eid: str, attrs: dict) -> bool:
        return eid.startswith("binary_sensor.") and (
            "cloud_connection_state" in eid
            or attrs.get("device_class") == "connectivity"
            or eid in self.connectivity_entities
            or self._is_tado_api(eid, attrs))

    def _representative(self, did: str) -> str:
        if did in self._representatives:
            return self._representatives[did]
        registry = entity_registry.async_get(self.hass)
        device = device_registry.async_get(self.hass).async_get(did)
        name = ((device.name_by_user or device.name) if device else "") or ""
        best, best_score = "", 9999
        for entry in registry.entities.values():
            eid = entry.entity_id
            if entry.device_id != did or entry.disabled_by is not None or eid in self.excluded_entities:
                continue
            if self.hass.states.get(eid) is None:
                continue
            domain = eid.split(".", 1)[0]
            if domain not in DOMAINS:
                continue
            state = self.hass.states.get(eid)
            is_cloud = domain == "binary_sensor" and self._is_cloud(
                eid, dict(state.attributes) if state else {}
            )
            bad = (any(word in eid for word in ("firmware", "update", "identify", "battery", "child_lock", "restart", "diagnostic"))
                   or eid.endswith("_led")
                   or ("volume" in eid and not eid.endswith("_status") and domain != "media_player")
                   or eid.startswith("switch.automation_")
                   or ("connectivity" in eid and "tado" not in eid and not is_cloud))
            if bad:
                continue
            score = DOMAINS.index(domain) * 100
            if is_cloud:
                score = 0
            elif domain == "binary_sensor" and ("connection_state" in eid or "connectivity" in eid):
                score = 1
            elif domain == "binary_sensor" and eid.startswith("binary_sensor.hue_") and eid.endswith("_motion"):
                score = 2
            elif domain == "sensor" and ("_state" in eid or "_status" in eid):
                score = 40
            if domain == "switch" and "unifi_" in eid:
                score += 80
            if domain == "switch" and ("_enabled" in eid or "analytics" in eid):
                score += 150
            if name == "unifi-dmp" and eid.startswith("alarm_control_panel."):
                score = 0
            if (score, eid) < (best_score, best or "\uffff"):
                best, best_score = eid, score
        # Do not cache an empty choice: a device may add entities later.
        if best:
            self._representatives[did] = best
        return best

    def _monitored(self, eid: str, attrs: dict) -> bool:
        did = self._device_id(eid)
        if self._ignored(eid, did):
            return False
        if eid in self.connectivity_entities:
            return True
        if self._is_tado_api(eid, attrs):
            return True  # Both APIs even though on the same registered device.
        return eid == self._representative(did)

    def _info(self, eid: str, attrs: dict) -> dict:
        did = self._device_id(eid)
        device = device_registry.async_get(self.hass).async_get(did) if did else None
        area = area_registry.async_get(self.hass).async_get_area(device.area_id) if device and device.area_id else None
        name = ((device.name_by_user or device.name) if device else "") or eid
        return {
            "name": name,
            "area": area.name if area else "Unassigned",
            "scope": attrs.get("connectivity_scope", "device"),
            "integration": self._source_integration(eid),
            "cloud": self._is_cloud(eid, attrs),
            "failure_reason": str(attrs.get("failure_reason") or "Not provided"),
            "last_successful_update": str(attrs.get("last_successful_update") or "Not provided"),
        }

    @staticmethod
    def _health(value: str, cloud: bool) -> str:
        if cloud:
            return "bad" if value in UNHEALTHY_CONNECTION else ("good" if value == "on" else "uncertain")
        if value == "unavailable":
            return "bad"
        if value in {"unknown", ""}:
            return "uncertain"
        return "good"

    async def on_change(self, event: Event) -> None:
        if not self.started:
            return
        eid = event.data.get("entity_id", "")
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if not eid or new is None or (old and old.state == new.state):
            return
        attrs = dict(new.attributes)
        if old:
            attrs = {**old.attributes, **attrs}
        async with self.lock:
            if self._nonphysical_endpoint(eid):
                # Nonphysical service/zone incidents must never be revived
                # merely because an unrelated room entity changes state.
                if self._prune_nonphysical_incidents():
                    await self.save()
                return
            now = utcnow()
            # Close an expired window before recording the new transition.
            # Otherwise a late recovery would be added to the old summary.
            if self.state.due(now):
                await self._finish(now)
            tracked = eid in self.state.pending or eid in self.state.active
            if not tracked and not self._monitored(eid, attrs):
                return
            info = self._info(eid, attrs)
            if tracked:
                info["cloud"] = self.state.pending.get(eid, self.state.active.get(eid, info)).get("cloud", info["cloud"])
            previous_count = len(self.state.batch["events"]) if self.state.batch else 0
            was_pending = self.state.pending.get(eid)
            was_active = eid in self.state.active
            if self.state.observe(eid, self._health(new.state, info["cloud"]), info, now, self.window):
                await self.save()
                # Record even short outages that never generated an email.
                if self.history and not was_pending and not was_active and eid in self.state.pending:
                    await self.history.record(
                        "availability_event", event="PENDING",
                        entity_id=eid, name=info.get("name", eid),
                        area=info.get("area"), scope=info.get("scope"),
                        since=self.state.pending[eid].get("since"),
                        reason="Awaiting offline confirmation",
                    )
                elif self.history and was_pending and eid not in self.state.pending and not was_active:
                    await self.history.record(
                        "availability_event", event="SHORT_OUTAGE",
                        entity_id=eid, name=info.get("name", eid),
                        area=info.get("area"), scope=info.get("scope"),
                        since=was_pending.get("since"),
                        minutes=max(0, round(
                            (now - parse(was_pending["since"])).total_seconds() / 60, 2
                        )),
                        reason="Recovered before confirmation; no email sent",
                    )
                await self._record_new_availability_events(previous_count)
            await self._tick_locked(now)

    def _current_health(self, eid: str, stored: dict) -> str:
        current = self.hass.states.get(eid)
        return self._health(current.state, stored["cloud"]) if current else "uncertain"

    async def reconcile(self) -> None:
        """Re-evaluate confirmed/pending outages after a restart; seed new ones."""
        async with self.lock:
            self.started = True
            # Reclassify persisted incidents before sending overdue digests:
            # HA service objects and tado Zones are not physical endpoints.
            if self._prune_nonphysical_incidents():
                await self.save()
            when = utcnow()
            if self.state.due(when):
                await self._finish(when)
            touched = False
            registry = entity_registry.async_get(self.hass)
            candidates = set(self.state.pending) | set(self.state.active)
            for entry in registry.entities.values():
                eid = entry.entity_id
                state = self.hass.states.get(eid)
                if state and self._monitored(eid, dict(state.attributes)):
                    candidates.add(eid)
            previous_count = len(self.state.batch["events"]) if self.state.batch else 0
            for eid in candidates:
                current = self.hass.states.get(eid)
                if not current:
                    continue
                attrs = dict(current.attributes)
                info = self._info(eid, attrs)
                if eid in self.state.active or eid in self.state.pending:
                    stored = self.state.active.get(eid, self.state.pending.get(eid))
                    info["cloud"] = stored["cloud"]
                touched |= self.state.observe(eid, self._health(current.state, info["cloud"]), info, when, self.window)
            if touched:
                await self.save()
                await self._record_new_availability_events(previous_count)
            await self._tick_locked(when)

    async def on_timer(self, _: datetime) -> None:
        if not self.started:
            return
        async with self.lock:
            await self._tick_locked(utcnow())

    async def _tick_locked(self, now: datetime) -> None:
        # Flush before adding new confirmed events so a fixed window never slides.
        if self.state.due(now):
            await self._finish(now)
        changed = False
        for eid in self.state.pending_due(now, self.delay):
            stored = self.state.pending.get(eid)
            if not stored:
                continue
            health = self._current_health(eid, stored)
            if health == "good":
                self.state.pending.pop(eid, None)
                changed = True
            elif health == "bad":
                previous_count = len(self.state.batch["events"]) if self.state.batch else 0
                confirmed = self.state.confirm(eid, now, self.window)
                changed |= confirmed
                if confirmed:
                    await self._record_new_availability_events(previous_count)
        if changed:
            await self.save()
        if self.state.initial_needed() and not self.state.due(now):
            await self._first_notification()

    async def _send(self, title: str, message: str) -> bool:
        try:
            await self.hass.services.async_call(
                "notify", "send_message",
                {"title": title, "message": message},
                target={"entity_id": self.notify_entity},
                blocking=True,
            )
            return True
        except Exception:  # Keep state for retry if notify provider fails.
            _LOGGER.exception("Device availability digest email failed; will retry")
            return False

    def _subject(self, detail: str) -> str:
        """Prepend the UI-configured subject label without double spaces."""
        return format_subject(self.subject_prefix, detail)

    def _when(self, ts: str) -> str:
        return dt_util.as_local(parse(ts)).strftime("%Y-%m-%d %H:%M:%S %Z")

    async def _first_notification(self) -> None:
        batch = self.state.batch
        if not batch:
            return
        outages = [e for e in batch["events"] if e["kind"] == "OFFLINE"]
        if not outages:
            return
        first = outages[0]
        suffix = f" (+{len(outages) - 1} other outages)" if len(outages) > 1 else ""
        title = self._subject(f"OFFLINE: {first['name']}{suffix}")
        message = (f"Confirmed offline for at least {int(self.delay.total_seconds() / 60)} minutes: "
                   f"{first['name']} ({first['area']})\n"
                   f"Entity: {first['entity_id']}\n"
                   f"First detected: {self._when(first['since'])}\n"
                   f"Monitoring window ends: {self._when(batch['deadline'])}\n"
                   "Further offline/recovery events will be collected in one summary.")
        if await self._send(title, message):
            batch["immediate_sent"] = True
            await self.save()
            if self.history:
                await self.history.record(
                    "availability_digest", event="INITIAL_EMAIL",
                    title=title, opened=batch["opened"],
                    deadline=batch["deadline"],
                    offline_count=len(outages),
                )

    async def _finish(self, now: datetime) -> None:
        batch = self.state.batch
        if not batch:
            return
        events = batch["events"]
        outages = [e for e in events if e["kind"] == "OFFLINE"]
        recoveries = [e for e in events if e["kind"] == "RECOVERED"]
        involved = {e["entity_id"] for e in events}
        outstanding = involved & self.state.active.keys()
        title = self._subject(
            f"AVAILABILITY SUMMARY: {len(involved)} monitored items; "
            f"{len(outstanding)} still offline"
        )
        lines = [
            f"Window: {self._when(batch['opened'])} to {self._when(batch['deadline'])}",
            f"Confirmed offline events: {len(outages)}",
            f"Recovery events: {len(recoveries)}",
            f"Still offline among these items: {len(outstanding)}",
            f"Other ongoing outages from earlier windows: {len(self.state.active.keys() - involved)}",
            "",
            "EVENTS (chronological):",
        ]
        for e in events:
            name = e["name"]
            if e["scope"] in {"main_api", "settings_api"}:
                name += f" / {e['scope']}"
            stamp = self._when(e["at"])
            line = f"{stamp} | {e['kind']} | {name} | {e['area']} | {e['entity_id']}"
            if e["kind"] == "OFFLINE":
                line += f" | disconnected since {self._when(e['since'])}"
                if e.get("scope") in {"main_api", "settings_api"}:
                    line += f" | cause: {e['failure_reason']} | last update: {e['last_successful_update']}"
            else:
                line += f" | duration approx. {e['minutes']} minutes"
            lines.append(line)
        if outstanding:
            lines.extend(["", "STILL OFFLINE:"])
            for eid in sorted(outstanding):
                info = self.state.active[eid]
                lines.append(f"- {info['name']} ({info['area']}) / {eid} / since {self._when(info['since'])}")
        if await self._send(title, "\n".join(lines)):
            self.state.batch = None
            await self.save()
            if self.history:
                await self.history.record(
                    "availability_digest", event="SUMMARY_EMAIL",
                    title=title, opened=batch["opened"],
                    deadline=batch["deadline"],
                    offline_count=len(outages),
                    recovered_count=len(recoveries),
                    remaining_offline=len(outstanding),
                    involved_entities=sorted(involved),
                )
