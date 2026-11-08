"""Pure state machine for durable Home Assistant availability digests.

All timestamps are ISO-8601 UTC. The caller persists snapshot() after each
change and restores it across HA restarts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def format_subject(prefix: str, detail: str) -> str:
    """Format alert subjects using a per-instance prefix from configuration."""
    return f"{prefix.strip()} {detail}".strip()


def is_service_device(entry_type: object) -> bool:
    """True for registry service/virtual devices, not physical devices."""
    return getattr(entry_type, "value", entry_type) == "service"


def is_nonphysical_device(entry_type: object, manufacturer: object, model: object) -> bool:
    """Exclude logical HA services and tado heating zones, never real hardware.

    Tado uses a regular HA device-registry entry for each logical room/Zone,
    rather than setting entry_type=service. Physical tado thermostats use
    distinct hardware models, and the API status sensors belong to model Home.
    """
    return is_service_device(entry_type) or (
        str(manufacturer or "").strip().casefold() == "tado"
        and str(model or "").strip().casefold() == "zone"
    )


class AvailabilityState:
    """Pending, active and digest-window state, suitable for JSON storage."""

    def __init__(self, saved: dict[str, Any] | None = None) -> None:
        saved = saved or {}
        self.pending: dict[str, dict] = saved.get("pending", {})
        self.active: dict[str, dict] = saved.get("active", {})
        self.batch: dict | None = saved.get("batch")

    def snapshot(self) -> dict:
        return {"pending": self.pending, "active": self.active, "batch": self.batch}

    def discard_entities(self, entity_ids: set[str]) -> bool:
        """Silently retire entities excluded by current monitoring policy.

        Unlike a recovery, withdrawing a virtual device should not generate
        another alert. Keep unrelated active incidents and queued events.
        """
        changed = False
        for eid in entity_ids:
            if self.pending.pop(eid, None) is not None:
                changed = True
            if self.active.pop(eid, None) is not None:
                changed = True
        if self.batch is not None:
            existing = self.batch["events"]
            remaining = [evt for evt in existing if evt["entity_id"] not in entity_ids]
            if len(remaining) != len(existing):
                changed = True
                if remaining:
                    self.batch["events"] = remaining
                else:
                    self.batch = None
        return changed

    def observe(self, entity_id: str, health: str, info: dict, when: datetime, window: timedelta) -> bool:
        """Record a state observation; health is 'bad', 'good' or 'uncertain'."""
        if health == "uncertain":
            return False
        if health == "bad":
            if entity_id in self.active or entity_id in self.pending:
                return False
            self.pending[entity_id] = {**info, "since": when.isoformat()}
            return True
        changed = self.pending.pop(entity_id, None) is not None
        if (previous := self.active.pop(entity_id, None)) is not None:
            elapsed = max(0, round((when - parse(previous["since"])).total_seconds() / 60))
            self._event(entity_id, "RECOVERED", {**previous, **info, "minutes": elapsed}, when, window)
            changed = True
        return changed

    def confirm(self, entity_id: str, when: datetime, window: timedelta) -> bool:
        """Promote an outage after caller confirms it is still unhealthy."""
        previous = self.pending.pop(entity_id, None)
        if previous is None or entity_id in self.active:
            return False
        self.active[entity_id] = previous
        self._event(entity_id, "OFFLINE", previous, when, window)
        return True

    def _event(self, eid: str, kind: str, info: dict, when: datetime, window: timedelta) -> None:
        if self.batch is None:
            self.batch = {
                "opened": when.isoformat(),
                "deadline": (when + window).isoformat(),
                "immediate_sent": False,
                "events": [],
            }
        self.batch["events"].append({
            "entity_id": eid,
            "kind": kind,
            "at": when.isoformat(),
            "since": info.get("since"),
            "name": info.get("name", eid),
            "integration": info.get("integration", "unknown"),
            "area": info.get("area", "Unassigned"),
            "scope": info.get("scope", "device"),
            "failure_reason": info.get("failure_reason"),
            "last_successful_update": info.get("last_successful_update"),
            "minutes": info.get("minutes"),
        })

    def due(self, now: datetime) -> bool:
        return self.batch is not None and now >= parse(self.batch["deadline"])

    def pending_due(self, now: datetime, delay: timedelta) -> list[str]:
        return [eid for eid, data in self.pending.items()
                if now >= parse(data["since"]) + delay]

    def initial_needed(self) -> bool:
        return self.batch is not None and not self.batch["immediate_sent"] and any(
            item["kind"] == "OFFLINE" for item in self.batch["events"]
        )
