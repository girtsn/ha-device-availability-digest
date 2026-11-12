# Device Availability Digest v0.3.14

## PM2.5 detection

- Classify genuinely implausible near-zero, low-variation PM2.5 readings as
  **STALE / pm25_stuck_low** after a 24-hour self-only observation period.
- Allow occasional 2–5 µg/m³ readings without clearing the diagnosis.
- Require a sustained increase above 5 µg/m³ for at least 45 minutes for
  recovery. Brief spikes cannot clear existing stale flags.
- Capture actual Home Assistant PM2.5 value changes between the 15-minute
  checks, preserving short spikes that prior snapshots could miss. Observations
  remain bounded and restart-persistent.
- Keep separate no-report, invalid-state, unchanged-value and stuck-low
  reasons; display report age, unchanged age and PM2.5 window independently.

## Reduce false positives

- Automatically exclude control/setpoint/target temperatures, programme
  progress, sauna standby status, SMA power-limitation settings and similar
  non-measurement readings.
- Continue to monitor genuine numeric physical measurements; existing
  `stale_monitor_include` and `stale_monitor_ignore` labels override the
  automatic policy.

## Notification reliability and diagnostics

- Notify on new flags, cleared flags **and changed classifications**.
- Continue change digests at 08:00 and 20:00 local time.
- Optionally remind once at 08:00 each day while unresolved measurements
  remain (enabled by default; configurable in integration Options).
- Show configured notify target, last delivery attempt, success/failure and
  error on the Stale sensors panel. Failed calls are recorded as EMAIL_FAILED
  events and their queued changes remain pending for retry.
- Note that provider acceptance does not guarantee mailbox delivery.

## Upgrade

Install via HACS/Marketplace and restart Home Assistant. Confirm the stale
notification target and daily reminder setting in the integration's Options.
Open Availability → Stale sensors → All monitored to audit coverage.
A new installation needs approximately 24 hours of PM2.5 observations;
saved v0.3.11+ samples are reused.
