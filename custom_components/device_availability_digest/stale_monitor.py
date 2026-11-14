"""Restart-safe stale physical-sensor monitor with quiet twice-daily digests.

Runs every 15 minutes. This is intentionally separate from the device outage
state machine: missing numeric measurements and loss of device connectivity
are different incidents. No global state_reported event listener is required.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from math import isfinite
import logging
from typing import Any, Awaitable, Callable

from homeassistant.helpers import device_registry, entity_registry, label_registry
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import is_nonphysical_device
from .stale_logic import (
    BAD_STATES, PM25_LOW_VARIATION_HOURS, classify, eligible_measurement,
    group_for, is_pm25, pm25_low_variation_details, timeout_hours,
    retained_stale_events, is_redundant_sma_grid_import,
)

_LOGGER = logging.getLogger(__name__)
STORE_KEY = DOMAIN + "_stale_measurements"
LABELS = {
    "stale_monitor_include", "stale_monitor_ignore",
    "stale_monitor_fast", "stale_monitor_slow",
    "stale_monitor_watch_value",
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo is not None else None
    except ValueError:
        return None


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _label_names(hass, entry) -> set[str]:
    """Resolve label IDs and display names; entity labels only."""
    all_labels = label_registry.async_get(hass)
    known = {
        label.label_id: {label.label_id.casefold(),
                         label.name.casefold().replace(" ", "_")}
        for label in all_labels.async_list_labels()
    }
    return {label for label_id in entry.labels
            for label in known.get(label_id, {str(label_id).casefold()})
            if label in LABELS}


class StaleSensorMonitor:
    def __init__(
        self, hass, send: Callable[[str, str], Awaitable[bool]],
        subject: Callable[[str], str], history,
        notify_target: Callable[[], str] | None = None,
        delivery_error: Callable[[], str | None] | None = None,
        daily_reminder: bool = True,
        pm25_window_hours: int = PM25_LOW_VARIATION_HOURS,
        pm25_high_threshold: float = 5.0,
        pm25_recovery_minutes: int = 45,
    ) -> None:
        self.hass = hass
        self.send = send
        self.subject = subject
        self.history = history
        self.notify_target = notify_target or (lambda: "")
        self.delivery_error = delivery_error or (lambda: None)
        self.daily_reminder = daily_reminder
        self.pm25_window_hours = pm25_window_hours
        self.pm25_high_threshold = pm25_high_threshold
        self.pm25_recovery_minutes = pm25_recovery_minutes
        self.store = Store(hass, 1, STORE_KEY, private=True, atomic_writes=True)
        self.lock = asyncio.Lock()
        self.active: dict[str, dict[str, Any]] = {}
        self.bad_since: dict[str, str] = {}
        self.pm25_samples: dict[str, list[list]] = {}
        self.queue: list[dict[str, Any]] = []
        self.last_digest: str | None = None
        self.last_attempt: str | None = None
        self.last_attempt_success: bool | None = None
        self.last_error: str | None = None
        self.last_target: str | None = None
        self.last_reminder_date: str | None = None
        self.checked_at: str | None = None
        self.rows: list[dict[str, Any]] = []
        self.started = False

    async def load(self) -> None:
        data = await self.store.async_load() or {}
        self.active = dict(data.get("active") or {})
        self.bad_since = dict(data.get("bad_since") or {})
        self.pm25_samples = dict(data.get("pm25_samples") or {})
        self.queue = list(data.get("queue") or [])[-1000:]
        self.last_digest = data.get("last_digest")
        self.last_attempt = data.get("last_attempt")
        self.last_attempt_success = data.get("last_attempt_success")
        self.last_error = data.get("last_error")
        self.last_target = data.get("last_target")
        self.last_reminder_date = data.get("last_reminder_date")

    async def _save(self) -> None:
        await self.store.async_save({
            "active": self.active, "bad_since": self.bad_since,
            "pm25_samples": self.pm25_samples,
            "queue": self.queue[-1000:], "last_digest": self.last_digest,
            "last_attempt": self.last_attempt,
            "last_attempt_success": self.last_attempt_success,
            "last_error": self.last_error,
            "last_target": self.last_target,
            "last_reminder_date": self.last_reminder_date,
        })

    def _details(self, entity_id: str, state, registry_entry, group: str) -> dict:
        device = None
        if registry_entry and registry_entry.device_id:
            device = device_registry.async_get(self.hass).async_get(registry_entry.device_id)
        area = None
        if registry_entry and registry_entry.area_id:
            area = registry_entry.area_id
        elif device:
            area = device.area_id
        from homeassistant.helpers import area_registry
        area_obj = area_registry.async_get(self.hass).async_get_area(area) if area else None
        return {
            "entity_id": entity_id,
            "name": state.name,
            "area": area_obj.name if area_obj else "Unassigned",
            "integration": registry_entry.platform if registry_entry else "unknown",
            "group": group,
        }

    async def observe_pm25_change(self, event) -> None:
        """Capture real HA PM2.5 value transitions between 15-minute scans.

        This supplements checkpoints so that even brief high-value excursions
        participate in the time-weighted anomaly assessment. The private
        history is bounded and never compares rooms or other devices.
        """
        new = event.data.get("new_state")
        old = event.data.get("old_state")
        eid = event.data.get("entity_id", "")
        if new is None or not eid.startswith("sensor.") or (
            old is not None and old.state == new.state
        ):
            return
        entry = entity_registry.async_get(self.hass).async_get(eid)
        if entry is None or entry.disabled_by is not None:
            return
        attrs = dict(new.attributes)
        if not is_pm25(eid, str(attrs.get("device_class") or "")):
            return
        labels = _label_names(self.hass, entry)
        device = (device_registry.async_get(self.hass).async_get(entry.device_id)
                  if entry.device_id else None)
        nonphysical = bool(device and is_nonphysical_device(
            device.entry_type, device.manufacturer, device.model
        ))
        category = getattr(entry.entity_category, "value", entry.entity_category)
        if not eligible_measurement(
            eid, new.state, attrs, bool(entry.device_id), category,
            labels, nonphysical, friendly_name=new.name,
            original_name=str(getattr(entry, "original_name", "") or ""),
        ):
            return
        when = getattr(new, "last_changed", None) or dt_util.utcnow()
        async with self.lock:
            cutoff = when - timedelta(hours=self.pm25_window_hours, minutes=30)
            history = [
                entry for entry in self.pm25_samples.get(eid, [])
                if (_parse_datetime(entry[0]) or datetime.min.replace(
                    tzinfo=timezone.utc)) >= cutoff
            ]
            if new.state in BAD_STATES:
                history = []  # an unavailable period breaks continuity
            else:
                try:
                    numeric = float(new.state)
                except (ValueError, TypeError):
                    return
                if not isfinite(numeric):
                    return
                history.append([_iso(when), numeric])
            self.pm25_samples[eid] = history[-3000:]
            await self._save()

    async def scan(self, send_digest: bool = False) -> None:
        """Re-evaluate sensor reports. The twice-daily call also sends deltas."""
        async with self.lock:
            now = dt_util.utcnow()
            registry = entity_registry.async_get(self.hass)
            devices = device_registry.async_get(self.hass)
            old_active = self.active
            previous_bad = self.bad_since
            next_active: dict[str, dict] = {}
            next_bad: dict[str, str] = {}
            rows: list[dict] = []
            transitions: list[dict] = []
            tracked_pm25: set[str] = set()
            live_pm25: dict[str, float] = {}
            has_shm2_import = (
                self.hass.states.get("sensor.shm2_em_metering_power_absorbed") is not None
            )
            for state in self.hass.states.async_all("sensor"):
                eid = state.entity_id
                entry = registry.async_get(eid)
                if entry and entry.disabled_by is not None:
                    continue
                labels = _label_names(self.hass, entry) if entry else set()
                # The optional SBSE grid-import channel duplicates the SHM2 meter.
                # No HA label is created; explicit include remains an override.
                if (is_redundant_sma_grid_import(eid, has_shm2_import)
                        and "stale_monitor_include" not in labels):
                    continue
                device = devices.async_get(entry.device_id) if entry and entry.device_id else None
                nonphysical = bool(device and is_nonphysical_device(
                    device.entry_type, device.manufacturer, device.model
                ))
                category = getattr(entry.entity_category, "value", entry.entity_category) if entry else None
                attrs = dict(state.attributes)
                if not eligible_measurement(
                    eid, state.state, attrs,
                    bool(entry and entry.device_id), category, labels, nonphysical,
                    friendly_name=state.name,
                    original_name=str(getattr(entry, "original_name", "") or ""),
                ):
                    # Registry and current eligibility are authoritative.
                    # Never resurrect an excluded entity just because it was
                    # previously flagged, including during unknown/unavailable.
                    continue
                group = group_for(eid, str(attrs.get("device_class") or ""))
                if is_pm25(eid, str(attrs.get("device_class") or "")):
                    tracked_pm25.add(eid)
                    try:
                        numeric = float(state.state)
                    except (ValueError, TypeError):
                        pass
                    else:
                        if isfinite(numeric):
                            live_pm25[eid] = numeric
                threshold = timeout_hours(group, labels)
                changed = state.last_changed
                reported = getattr(state, "last_reported", None) or state.last_updated
                bad = state.state in BAD_STATES
                if bad:
                    previous = _parse_datetime(self.bad_since.get(eid))
                    # Preserve an existing old timestamp through a restart;
                    # never reset the unknown/unavailable dwell timer each poll.
                    bad_at = min(changed, previous) if previous else changed
                    next_bad[eid] = _iso(bad_at)
                else:
                    bad_at = None
                status, reason, age, limit = classify(
                    now=now, state=state.state, last_reported=reported,
                    last_changed=changed, bad_since=bad_at, timeout=threshold,
                    group=group, frozen_watch="stale_monitor_watch_value" in labels,
                )
                row = {
                    **self._details(eid, state, entry, group),
                    "value": state.state,
                    "unit": str(attrs.get("unit_of_measurement") or ""),
                    "status": status,
                    "reason": reason,
                    "age_hours": round(age, 2),
                    "report_age_hours": round(max(0, (now - reported).total_seconds() / 3600), 2),
                    "unchanged_hours": round(max(0, (now - changed).total_seconds() / 3600), 2),
                    "threshold_hours": limit,
                    "last_reported": _iso(reported),
                    "last_changed": _iso(changed),
                    "bad_since": _iso(bad_at) if bad_at else None,
                    "frozen_watch": "stale_monitor_watch_value" in labels,
                }
                rows.append(row)
                if status in {"stale", "suspect"}:
                    next_active[eid] = row

            # Keep a short rolling PM2.5 history across restarts. Observe only
            # selected physical PM2.5 sensors, not any diagnostic entities.
            # Samples are taken on the existing 15-minute scans, not via a
            # global state-report listener or Recorder/history queries.
            # Retain at least one checkpoint preceding the left window edge
            # so the entire configured period can be time-weighted.
            cutoff = now - timedelta(hours=self.pm25_window_hours, minutes=30)
            windows: dict[str, list[tuple[datetime, float]]] = {}
            samples: dict[str, list[list]] = {}
            for eid in tracked_pm25:
                window: list[tuple[datetime, float]] = []
                for sample in self.pm25_samples.get(eid, []):
                    if not isinstance(sample, (list, tuple)) or len(sample) != 2:
                        continue
                    when = _parse_datetime(sample[0])
                    if when is None or not cutoff <= when <= now:
                        continue
                    try:
                        number = float(sample[1])
                    except (TypeError, ValueError):
                        continue
                    if isfinite(number):
                        window.append((when, number))
                window.sort(key=lambda item: item[0])
                latest = live_pm25.get(eid)
                if latest is not None and (
                    not window or (now - window[-1][0]).total_seconds() >= 600
                ):
                    window.append((now, latest))
                windows[eid] = window
                samples[eid] = [[_iso(when), number] for when, number in window]

            # Detect a sensor's own nearly motionless 0–2 µg/m³ PM2.5
            # history. No peer or other sensor is ever consulted. Even when
            # readings vary slightly, 48h of near-zero values can be suspect.
            # A fresh HA report is required; no-report is checked separately.
            for row in rows:
                eid = row["entity_id"]
                if (row["status"] not in {"healthy", "suspect"} or eid not in windows
                        or row["age_hours"] > 1):
                    continue
                assessment = pm25_low_variation_details(
                    windows[eid], now, window_hours=self.pm25_window_hours,
                    recovery_threshold=self.pm25_high_threshold,
                    recovery_minutes=self.pm25_recovery_minutes,
                )
                row["low_variation_hours"] = assessment["window_hours"]
                row["pm25_low_fraction"] = assessment["low_fraction"]
                row["pm25_max_high_minutes"] = assessment["max_high_minutes"]
                was_stuck_low = (old_active.get(eid, {}).get("reason") == "pm25_stuck_low")
                if assessment["stuck"] or (was_stuck_low and not assessment["sustained_high"]):
                    row["status"] = "stale"
                    row["reason"] = "pm25_stuck_low"
                    row["age_hours"] = assessment["window_hours"]
                    row["threshold_hours"] = float(self.pm25_window_hours)

            samples_changed = samples != self.pm25_samples
            self.pm25_samples = samples
            next_active = {
                row["entity_id"]: row for row in rows
                if row["status"] in {"stale", "suspect"}
            }

            eligible_ids = {row["entity_id"] for row in rows}
            retired = set(old_active) - eligible_ids
            # Retired controls must not send stale/recovery emails. Retain
            # diagnostic history but purge any not-yet-delivered queue items.
            previous_queue_count = len(self.queue)
            self.queue = retained_stale_events(self.queue, eligible_ids)

            for eid, row in next_active.items():
                if eid not in old_active:
                    transitions.append({
                        "event": "FLAGGED", "at": _iso(now), **row,
                    })
                elif (old_active[eid].get("status"), old_active[eid].get("reason")) != (row["status"], row["reason"]):
                    transitions.append({
                        "event": "RECLASSIFIED", "at": _iso(now), **row,
                    })
            for eid, old in old_active.items():
                if eid not in next_active and eid in eligible_ids:
                    current = next(r for r in rows if r["entity_id"] == eid)
                    transitions.append({
                        "event": "CLEARED", "at": _iso(now),
                        **current,
                        "reason": "reporting_again",
                    })
            self.active = next_active
            self.bad_since = next_bad
            self.rows = sorted(
                rows, key=lambda r: (
                    0 if r["status"] == "stale" else
                    1 if r["status"] == "suspect" else
                    2 if r["status"] == "pending" else 3,
                    -r["age_hours"], r["entity_id"],
                )
            )
            self.checked_at = _iso(now)
            self.started = True
            if transitions:
                self.queue.extend(transitions)
                self.queue = self.queue[-1000:]
                if self.history:
                    for item in transitions:
                        await self.history.record(
                            "stale_measurement", event=item["event"],
                            entity_id=item["entity_id"], name=item["name"],
                            area=item["area"], group=item["group"],
                            reason=item["reason"], status=item["status"],
                            value=item["value"], age_hours=item["age_hours"],
                            threshold_hours=item["threshold_hours"],
                        )
            # Persist any transition or bad-state timer change, not hourly
            # age changes; measurements are rebuilt from live HA states.
            if (transitions or retired or len(self.queue) != previous_queue_count
                    or next_bad != previous_bad or samples_changed):
                await self._save()
            if send_digest:
                await self._digest(now)

    def snapshot(self) -> dict:
        status_count = {
            kind: sum(row["status"] == kind for row in self.rows)
            for kind in ("healthy", "pending", "stale", "suspect")
        }
        return {
            "enabled": True, "started": self.started,
            "checked_at": self.checked_at,
            "last_digest": self.last_digest,
            "last_attempt": self.last_attempt,
            "last_attempt_success": self.last_attempt_success,
            "last_error": self.last_error,
            "last_target": self.last_target,
            "notification_target": self.notify_target(),
            "daily_reminder_enabled": self.daily_reminder,
            "pm25_window_hours": self.pm25_window_hours,
            "pm25_high_threshold": self.pm25_high_threshold,
            "pm25_recovery_minutes": self.pm25_recovery_minutes,
            "queued_events": len(self.queue),
            "counts": {"monitored": len(self.rows), **status_count},
            "rows": self.rows,
        }

    async def _digest(self, now: datetime) -> None:
        """Send queued changes at 08:00/20:00 and one optional daily reminder."""
        local = dt_util.as_local(now)
        morning = local.hour == 8
        today = local.date().isoformat()
        reminder = bool(
            self.daily_reminder and morning and self.active
            and self.last_reminder_date != today
        )
        if not self.queue and not reminder:
            return
        queued = list(self.queue)
        newly = [e for e in queued if e["event"] == "FLAGGED"]
        cleared = [e for e in queued if e["event"] == "CLEARED"]
        reclassified = [e for e in queued if e["event"] == "RECLASSIFIED"]
        detail = (f"SENSOR MEASUREMENTS: {len(newly)} flagged, "
                  f"{len(reclassified)} reclassified, {len(cleared)} cleared")
        if reminder and not queued:
            detail = f"SENSOR MEASUREMENTS: daily reminder ({len(self.active)} unresolved)"
        title = self.subject(detail)
        lines = [
            "Stale numeric measurement digest (changes and unresolved reminders)",
            "Checked: " + local.strftime("%Y-%m-%d %H:%M:%S %Z"),
            f"Monitored: {len(self.rows)} | Stale: {len([r for r in self.rows if r['status'] == 'stale'])}"
            f" | Suspect: {len([r for r in self.rows if r['status'] == 'suspect'])}",
            "",
            "EVENTS (chronological):",
        ]
        for item in queued:
            at = _parse_datetime(item["at"])
            at_text = dt_util.as_local(at).strftime("%Y-%m-%d %H:%M %Z") if at else item["at"]
            lines.append(
                f"{at_text} | {item['event']} | {item['name']} | {item['entity_id']}"
                f" | {item['reason']} | value {item['value']} {item['unit']}"
                f" | {item['age_hours']}h / {item['threshold_hours']}h threshold"
            )
        if not queued:
            lines.append("No new changes; daily unresolved reminder.")
        if self.active:
            lines.extend(["", f"CURRENTLY FLAGGED ({len(self.active)}):"])
            for row in sorted(self.active.values(), key=lambda r: r["entity_id"]):
                lines.append(
                    f"- {row['name']} / {row['entity_id']} / {row['status']} "
                    f"({row['reason']}; {row['age_hours']}h of {row['threshold_hours']}h)"
                )
        lines.extend(["", "Unknown/unavailable states use a dwell period.",
                      "Persistently near-zero PM2.5 may be classified STALE with reason pm25_stuck_low.",
                      "Review the Stale sensors tab in the Availability dashboard."])
        self.last_attempt = _iso(now)
        self.last_target = self.notify_target()
        success = await self.send(title, "\n".join(lines))
        self.last_attempt_success = success
        if success:
            self.queue = self.queue[len(queued):]
            self.last_digest = _iso(now)
            self.last_error = None
            if reminder:
                self.last_reminder_date = today
            await self._save()
            if self.history:
                await self.history.record(
                    "stale_digest", event="SUMMARY_EMAIL",
                    title=title, flagged_count=len(newly),
                    reclassified_count=len(reclassified),
                    cleared_count=len(cleared), monitored_count=len(self.rows),
                    reminder=reminder,
                )
        else:
            self.last_error = self.delivery_error() or "Notification service rejected the message. See Home Assistant logs."
            await self._save()  # keep queue for retry at next scheduled slot
            if self.history:
                await self.history.record(
                    "stale_digest", event="EMAIL_FAILED",
                    title=title, target=self.last_target,
                    error=self.last_error,
                    queued_count=len(self.queue),
                )
