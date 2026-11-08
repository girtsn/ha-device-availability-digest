# Device Availability Digest v0.3.3 — fix dropped device-availability events

## Fixed

- Correct the Home Assistant AreaRegistry lookup from `async_get(area_id)` to
  `async_get_area(area_id)` when determining a device's room.
- Previously, any monitored entity assigned to an area could raise
  `AttributeError` inside `_info()`, preventing its outage from entering
  pending/confirmed monitoring. This also caused repeated background task errors.
- Keep the original device-area label and the `Unassigned` fallback when no
  area exists.

## Verification

- Add offline regression tests that execute the actual `_info()` method from
  the integration source using Home Assistant-compatible registry stubs.
- Test named areas, unassigned devices, and deleted/unknown areas without
  requiring Home Assistant as a test dependency.

## Upgrade

Install v0.3.3 through HACS/Marketplace and restart Home Assistant. On startup,
the monitor reconciles current unavailable entities, then applies your configured
offline confirmation delay; it cannot recover exact transitions from the period
when the v0.3.2 monitor was failing.
