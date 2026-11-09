"""Privacy-minimal timestamps for household presence evidence.

Only entity IDs and timestamps are retained; no GPS coordinates or network
identifiers are copied into the last-Home cache.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

HOME_STATES = {"device_tracker": "home", "person": "home", "sensor": "home",
               "binary_sensor": "on", "input_boolean": "on"}


def reported_at(state: Any) -> str | None:
    """Actual HA report/update time; never use the time the panel was opened.

    State.last_reported is preferred when provided by HA. It advances when HA
    accepts a state report even if its value and attributes do not change.
    Older versions can fall back to last_updated (not a GPS heartbeat).
    """
    if state is None:
        return None
    value = getattr(state, "last_reported", None) or getattr(state, "last_updated", None)
    if not isinstance(value, datetime) or value.tzinfo is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def is_home_source(entity_id: str, state: Any) -> bool:
    """State semantics agree with the integration's Home Presence label."""
    if state is None:
        return False
    domain = entity_id.partition(".")[0]
    return getattr(state, "state", None) == HOME_STATES.get(domain)


def latest_timestamps(existing: dict[str, str], observations: dict[str, str]) -> dict[str, str]:
    """Merge monotonic timestamps; stale out-of-order updates cannot roll back Home."""
    result = dict(existing)
    for entity_id, value in observations.items():
        if not isinstance(entity_id, str) or not entity_id or not isinstance(value, str):
            continue
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if timestamp.tzinfo is None:
                continue
            stamp = timestamp.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue
        if entity_id not in result or stamp > result[entity_id]:
            result[entity_id] = stamp
    return result
