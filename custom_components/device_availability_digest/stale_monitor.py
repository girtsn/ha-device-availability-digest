"""Restart-safe stale physical-sensor monitor with quiet twice-daily digests.

Runs every 15 minutes. This is intentionally separate from the device outage
state machine: missing numeric measurements and loss of device connectivity
are different incidents. No global state_reported event listener is required.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, Awaitable, Callable

from homeassistant.helpers import device_registry, entity_registry, label_registry
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .model import is_nonphysical_device
from .stale_logic import BAD_STATES, classify, eligible_measurement, group_for, timeout_hours

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
    ) -> None:
        self.hass = hass
        self.send = send
        self.subject = subject
        self.history = history
        self.store = Store(hass, 1, STORE_KEY, private=True, atomic_writes=True)
        self.lock = asyncio.Lock()
        self.active: dict[str, dict[str, Any]] = {}
        self.bad_since: dict[str, str] = {}
        self.queue: list[dict[str, Any]] = []
        self.last_digest: str | None = None
        self.checked_at: str | None = None
        self.rows: list[dict[str, Any]] = []
        self.started = False

    async def load(self) -> None:
        data = await self.store.async_load() or {}
        self.active = dict(data.get("active") or {})
        self.bad_since = dict(data.get("bad_since") or {})
        self.queue = list(data.get("queue") or [])[-1000:]
        self.last_digest = data.get("last_digest")

    async def _save(self) -> None:
        await self.store.async_save({
            "active": self.active, "bad_since": self.bad_since,
            "queue": self.queue[-1000:], "last_digest": self.last_digest,
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
            for state in self.hass.states.async_all("sensor"):
                eid = state.entity_id
                entry = registry.async_get(eid)
                if entry and entry.disabled_by is not None:
                    continue
                labels = _label_names(self.hass, entry) if entry else set()
                device = devices.async_get(entry.device_id) if entry and entry.device_id else None
                nonphysical = bool(device and is_nonphysical_device(
                    device.entry_type, device.manufacturer, device.model
                ))
                category = getattr(entry.entity_category, "value", entry.entity_category) if entry else None
                attrs = dict(state.attributes)
                if not eligible_measurement(
                    eid, state.state, attrs,
                    bool(entry and entry.device_id), category, labels, nonphysical
                ):
                    # Keep a previously flagged generic numeric sensor if it
                    # has temporarily become unavailable; explicit ignore wins.
                    if (eid not in old_active or "stale_monitor_ignore" in labels
                            or category in {"diagnostic", "config"} or nonphysical):
                        continue
                group = group_for(eid, str(attrs.get("device_class") or ""))
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
                    "threshold_hours": limit,
                    "last_reported": _iso(reported),
                    "last_changed": _iso(changed),
                    "bad_since": _iso(bad_at) if bad_at else None,
                    "frozen_watch": "stale_monitor_watch_value" in labels,
                }
                rows.append(row)
                if status in {"stale", "suspect"}:
                    next_active[eid] = row

            for eid, row in next_active.items():
                if eid not in old_active:
                    transitions.append({
                        "event": "FLAGGED", "at": _iso(now), **row,
                    })
            for eid, old in old_active.items():
                if eid not in next_active:
                    current = next((r for r in rows if r["entity_id"] == eid), None)
                    transitions.append({
                        "event": "CLEARED", "at": _iso(now),
                        **(current or old),
                        "reason": "reporting_again" if current else "removed_or_excluded",
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
            if transitions or next_bad != previous_bad:
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
            "queued_events": len(self.queue),
            "counts": {"monitored": len(self.rows), **status_count},
            "rows": self.rows,
        }

    async def _digest(self, now: datetime) -> None:
        if not self.queue:
            return
        queued = list(self.queue)
        newly = [e for e in queued if e["event"] == "FLAGGED"]
        cleared = [e for e in queued if e["event"] == "CLEARED"]
        title = self.subject(
            f"SENSOR MEASUREMENTS: {len(newly)} flagged, {len(cleared)} cleared"
        )
        lines = [
            "Stale numeric measurement digest (changes since previous email)",
            "Checked: " + dt_util.as_local(now).strftime("%Y-%m-%d %H:%M:%S %Z"),
            f"Monitored: {len(self.rows)} | Stale: {len([r for r in self.rows if r['status'] == 'stale'])}"
            f" | Suspected frozen: {len([r for r in self.rows if r['status'] == 'suspect'])}",
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
        if self.active:
            lines.extend(["", f"CURRENTLY FLAGGED ({len(self.active)}):"])
            for row in sorted(self.active.values(), key=lambda r: r["entity_id"]):
                lines.append(
                    f"- {row['name']} / {row['entity_id']} / {row['status']} "
                    f"({row['reason']}; {row['age_hours']}h of {row['threshold_hours']}h)"
                )
        lines.extend(["", "Unavailable and unknown states use a dwell period.",
                      "Unchanged-value findings are heuristic and require an opt-in label.",
                      "Review the Stale sensors tab in the Availability dashboard."])
        if await self.send(title, "\n".join(lines)):
            # A failed delivery retains the event queue until the next slot.
            self.queue = self.queue[len(queued):]
            self.last_digest = _iso(now)
            await self._save()
            if self.history:
                await self.history.record(
                    "stale_digest", event="SUMMARY_EMAIL",
                    title=title, flagged_count=len(newly),
                    cleared_count=len(cleared), monitored_count=len(self.rows),
                )
