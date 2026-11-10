# Device Availability Digest v0.3.11 — Self-contained PM2.5 stuck-sensor check

## Fixed
- Removed the cross-device/adjacent-room PM2.5 comparison introduced in v0.3.10. **No other sensor is consulted** to assess a PM2.5 measurement.
- Each physical PM2.5 sensor is independently flagged **SUSPECT** if its own 15-minute observations stay at 0–2 µg/m³ for at least 46 hours within a rolling 48-hour window, with at least 96 observations and a fresh HA report.
- Minor fluctuations of 0→1→2 µg/m³ no longer reset this check.
- The new rule is available to a home with only one PM2.5 sensor. A short clean-air period does not trigger it.
- The existing private Store carries readings over from v0.3.10 across Home Assistant restarts.
- Updated the Stale sensors dashboard wording, digest notes, tests and documentation.

## Important
- This is an advisory **SUSPECT** condition, not a confirmed stale report or device outage. Truly clean rooms can legitimately have sustained readings of 0–2 µg/m³. To ignore a particular sensor, apply `stale_monitor_ignore` to that entity.
- Existing no-report, unknown/unavailable, availability, Home Presence and notification settings are unchanged.
- Update in HACS/Marketplace and restart Home Assistant.
