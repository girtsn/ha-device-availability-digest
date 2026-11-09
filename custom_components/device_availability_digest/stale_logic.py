"""Pure rules for physical numeric measurements, independent of Home Assistant."""
from __future__ import annotations

from datetime import datetime
from math import isfinite

AIR = frozenset({
    "pm1", "pm10", "pm25", "carbon_dioxide", "carbon_monoxide",
    "volatile_organic_compounds", "volatile_organic_compounds_parts",
    "nitrogen_dioxide", "ozone",
})
AMBIENT = frozenset({"temperature", "humidity", "pressure", "illuminance"})
ELECTRICAL = frozenset({"power", "current", "voltage", "frequency"})
EXCLUDED_ID_PARTS = (
    "link_speed", "linkspeed", "link_quality", "rssi", "signal_strength",
    "uptime", "last_seen", "last_update", "firmware", "wifi_signal",
    "battery", "diagnostic", "packet", "retransmit", "download_speed",
    "upload_speed", "memory_usage", "cpu_usage",
)
BAD_STATES = frozenset({"unknown", "unavailable", ""})


def group_for(entity_id: str, device_class: str) -> str:
    """A small set of transparent thresholds, not a model-specific whitelist."""
    eid = entity_id.lower()
    dc = (device_class or "").lower()
    if dc in AIR or any(part in eid for part in ("voc_index", "pm2_5", "pm25", "pm10")):
        return "air"
    if dc in AMBIENT:
        return "ambient"
    if dc in ELECTRICAL:
        return "electrical"
    return "other"


def timeout_hours(group: str, labels: set[str]) -> int:
    if "stale_monitor_fast" in labels:
        return 3
    if "stale_monitor_slow" in labels:
        return 168
    return {"air": 12, "ambient": 48, "electrical": 72}.get(group, 168)


def eligible_measurement(
    entity_id: str,
    state: str,
    attributes: dict,
    device_linked: bool,
    category: str,
    labels: set[str],
    nonphysical: bool = False,
) -> bool:
    """Conservative automatic selection; explicit include overrides defaults."""
    if "stale_monitor_ignore" in labels:
        return False
    if "stale_monitor_include" in labels:
        return True
    if not device_linked or nonphysical or category in {"diagnostic", "config"}:
        return False
    if any(part in entity_id.lower() for part in EXCLUDED_ID_PARTS):
        return False
    if attributes.get("state_class") in {"total", "total_increasing"}:
        return False
    dc = str(attributes.get("device_class") or "")
    if dc in {"battery", "data_rate", "signal_strength", "duration", "timestamp",
              "enum", "monetary", "energy", "gas", "water", "volume", "data_size"}:
        return False
    # Availability states with a recognised physical measurement class
    # remain eligible even though their current value is not numeric.
    if dc in AIR | AMBIENT | ELECTRICAL or group_for(entity_id, dc) == "air":
        return True
    if state in BAD_STATES and (attributes.get("state_class") == "measurement"
                                or attributes.get("unit_of_measurement") not in (None, "")):
        return True
    try:
        numeric = isfinite(float(state))
    except (ValueError, TypeError):
        numeric = False
    return numeric and (attributes.get("state_class") == "measurement"
                        or attributes.get("unit_of_measurement") not in (None, ""))


def classify(
    *, now: datetime, state: str, last_reported: datetime,
    last_changed: datetime, bad_since: datetime | None,
    timeout: int, group: str, frozen_watch: bool = False,
) -> tuple[str, str, float, float]:
    """Return status, reason, report-age hours and threshold hours.

    A constant value with fresh reports is healthy unless explicitly opted
    into the heuristic via stale_monitor_watch_value. That heuristic reports
    SUSPECT, not a verified hardware outage.
    """
    age = max(0.0, (now - last_reported).total_seconds() / 3600)
    if state in BAD_STATES:
        grace = min(timeout, 12 if group == "air" else 24)
        since = bad_since or last_changed
        bad_age = max(0.0, (now - since).total_seconds() / 3600)
        if bad_age >= grace:
            return "stale", state or "unknown", bad_age, float(grace)
        return "pending", state or "unknown", bad_age, float(grace)
    if age >= timeout:
        return "stale", "no_report", age, float(timeout)
    if frozen_watch:
        unchanged = max(0.0, (now - last_changed).total_seconds() / 3600)
        if unchanged >= timeout:
            return "suspect", "unchanged_value", unchanged, float(timeout)
    return "healthy", "reporting", age, float(timeout)
