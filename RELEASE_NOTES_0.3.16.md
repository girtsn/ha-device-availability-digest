# Device Availability Digest v0.3.16

## Fix PM2.5 observation threshold mismatch

- Require a **complete configured observation window** before a new PM2.5
  stuck-low classification. Previously the 24-hour threshold allowed a
  measurement spanning only 23 hours and consequently the dashboard could
  show STALE at, for example, 23.89h / 24h.
- Preserve one checkpoint before the observation window boundary so that
  time-weighted evidence can reach the full period without depending on
  scans aligning with the exact boundary.
- Add regression tests for sub-threshold coverage, full 24-hour evidence
  and left-boundary sample carry-forward.

Includes all fixes from v0.3.15 (remove previously flagged operational
or configuration entries; no false recovery emails) and v0.3.14
(24-hour PM2.5 stuck-low rule, adjustable thresholds, notification
diagnostics and daily reminders).

## Upgrade

Update through HACS/Marketplace and restart Home Assistant.
The kitchen PM2.5 detection retains prior samples and will be flagged
when at least a full configured observation window has been observed.
