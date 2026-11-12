"""Pure rules for physical numeric measurements, independent of Home Assistant."""
from __future__ import annotations

from datetime import datetime, timedelta
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
    "program_progress", "programme_progress", "standby_active",
    "active_power_limitation", "power_limit", "target_temperature",
    "setpoint", "set_point", "effective_target", "control_mode",
    "upload_speed", "memory_usage", "cpu_usage",
)
BAD_STATES = frozenset({"unknown", "unavailable", ""})
PM25_LOW_VARIATION_HOURS = 24
PM25_MIN_SAMPLES = 64
PM25_HIGH_RECOVERY_MINUTES = 45
PM25_MAX_REPORT_GAP_MINUTES = 120
PM25_MIN_LOW_FRACTION = 0.70


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



def is_pm25(entity_id: str, device_class: str) -> bool:
    """Recognise PM2.5 measurements without matching unrelated numeric sensors."""
    eid = entity_id.lower()
    return (device_class or "").lower() == "pm25" or any(
        marker in eid for marker in ("pm2_5", "pm2.5", "pm25")
    )


def pm25_low_variation_details(
    own_samples: list[tuple[datetime, float]], now: datetime | None = None,
    *, window_hours: int = PM25_LOW_VARIATION_HOURS,
    recovery_threshold: float = 5.0,
    recovery_minutes: int = PM25_HIGH_RECOVERY_MINUTES,
) -> dict:
    """Identify a 24-hour stuck-low signal without treating small spikes as recovery.

    Use only this sensor's own samples. Samples include HA value-change
    events (to catch short spikes) and periodic checkpoints for coverage.
    Durations are time weighted: a few readings of 2-5 are acceptable, but
    a sensor that spends significant time there is not considered stuck.
    """
    result = {
        "stuck": False, "sustained_high": False, "window_hours": 0.0,
        "low_fraction": 0.0, "mid_fraction": 0.0,
        "max_high_minutes": 0.0, "sample_count": 0,
    }
    samples = sorted(
        ((when, float(value)) for when, value in own_samples
         if when.tzinfo is not None and isfinite(value)),
        key=lambda item: item[0],
    )
    if not samples:
        return result
    end = now or samples[-1][0]
    start = end - timedelta(hours=window_hours)
    # Carry forward the most recent value before the window if available,
    # rather than treating a missing beginning as fresh data.
    earlier = [sample for sample in samples if sample[0] < start]
    window = ([ (start, earlier[-1][1]) ] if earlier else []) + [
        (when, value) for when, value in samples if start <= when <= end
    ]
    result["sample_count"] = len(window)
    min_samples = max(12, round(PM25_MIN_SAMPLES * window_hours / PM25_LOW_VARIATION_HOURS))
    if len(window) < min_samples:
        return result
    coverage = (window[-1][0] - window[0][0]).total_seconds()
    result["window_hours"] = round(coverage / 3600, 2)
    if coverage < (window_hours - 1) * 3600:
        return result
    low_seconds = mid_seconds = high_seconds = 0.0
    high_run = max_high = 0.0
    for (when, value), (next_when, _) in zip(window, window[1:] + [(end, window[-1][1])]):
        duration = max(0.0, (next_when - when).total_seconds())
        if duration > PM25_MAX_REPORT_GAP_MINUTES * 60:
            return result  # insufficient observation continuity
        if value <= 1 and value >= 0:
            low_seconds += duration
        elif 1 < value <= recovery_threshold:
            mid_seconds += duration
        elif value > recovery_threshold:
            high_seconds += duration
        if value > recovery_threshold:
            high_run += duration
            max_high = max(max_high, high_run)
        else:
            high_run = 0.0
    total = max(1.0, (end - window[0][0]).total_seconds())
    result["low_fraction"] = round(low_seconds / total, 3)
    result["mid_fraction"] = round(mid_seconds / total, 3)
    result["max_high_minutes"] = round(max_high / 60, 2)
    result["sustained_high"] = max_high >= recovery_minutes * 60
    result["stuck"] = bool(
        result["low_fraction"] >= PM25_MIN_LOW_FRACTION
        and mid_seconds / total <= (1 - PM25_MIN_LOW_FRACTION)
        and high_seconds / total <= 0.1
        and not result["sustained_high"]
    )
    return result


def low_variation_pm25(own_samples: list[tuple[datetime, float]]) -> bool:
    """Compatibility wrapper for the self-only low-variation rule."""
    return pm25_low_variation_details(own_samples)["stuck"]


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
    if state in BAD_STATES and attributes.get("state_class") == "measurement":
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
