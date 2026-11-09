# Device Availability Digest v0.3.8 — Stale measurements

## Integrated stale sensor monitoring

- New **Stale sensors** tab in the managed **Availability** sidebar dashboard, with
  a real-time audit of monitored numeric sensors (healthy, pending, stale,
  suspected frozen), reporting timestamps, threshold and device/area details.
- 15-minute scans; **quiet delta-only emails at 08:00 and 20:00 local time**
  through a separately configured stale-notify entity and the existing subject
  prefix. `notify.email_girts` is preferred when available.
  Failed sends retain the queue; reports and last successful notification time
  survive restart in a **separate private Home Assistant Store**.
- Full entity IDs replace MD5-truncated Text-helper keys, removing the
  old 56-sensor state cap and missing/deleted entity ambiguity.
- Detect missing HA reports, long-lived unknown/unavailable states, and
  **opt-in suspected frozen readings** independently.
- Automatic selection of registered physical measurement sensors; ignore
  diagnostic/link-speed/total/battery/virtual sensors by default. Entity-level
  labels: `stale_monitor_include`, `stale_monitor_ignore`,
  `stale_monitor_fast`, `stale_monitor_slow`,
  `stale_monitor_watch_value`.
- Defaults: 12h air, 48h ambient, 72h electrical, 168h other;
  unknown/unavailable 12h air or 24h other grace (or shorter timeout).
- Reuse the existing administrator-only diagnostics API and 90-day event history,
  with search, filtering, and all-sensor coverage diagnostics.

## Compatibility and deployment

- Existing device availability, Home Presence, recovery digests and entity IDs
  are unaffected. The stale monitor is enabled by default and can be disabled in Options.
- **Disable the old stale sensor automation** after upgrading to avoid duplicate
  emails. The old Text helpers remain untouched and can be removed manually
  once the new monitor is verified.
- Home Assistant `last_reported` means HA received an entity state write,
  **not** proof a device sampled new data. Suspected frozen values are clearly
  distinguished from missing reports.
- Update via HACS and restart Home Assistant. Open
  **Availability → Stale sensors → All monitored** to validate selection.
- Python regression tests and frontend validation were added.
