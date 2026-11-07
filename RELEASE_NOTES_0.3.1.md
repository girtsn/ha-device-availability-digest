# Device Availability Digest v0.3.1 — dashboard mobile and history usability

## Availability sidebar

- Add the **Home Assistant hamburger menu** for mobile and narrow screens,
  using the same `hass-toggle-menu` event and responsive header as the
  existing Tado X and Tylö Sauna managed dashboards.
- Replace the fixed 24-hour / 7 / 30 / 90-day buttons with the **same shared
  date-range picker** as Tado X / Tylö Sauna: calendar start/end dates,
  presets (today, yesterday, week, month, quarter, year, rolling periods),
  and previous/next period navigation.
- Extend the administrator-only diagnostic-history API to accept an exact
  timezone-aware, end-exclusive calendar range, retaining compatibility
  with older clients using the `days` parameter.
- Make charts adapt to the chosen range with hourly, daily, weekly or
  monthly activity buckets. **History retention is still 90 days / 5,000
  events**; selecting a wider or older range does not fabricate events.

## Clearer Home Presence diagnostics

- Only report `old → new` when the actual presence/location state changes.
- If an HA Person's source tracker or a trusted labeled tracker's IP, MAC
  or SSID changes while its state remains unchanged, record a separate
  **DETAILS** diagnostic item with changed fields, rather than a misleading
  `home → home` transition.
- Legacy same-state records from v0.3.0 are displayed as detail updates.
- These changes affect event presentation only: Home/Away inference, Tado
  consumer behavior and availability-email logic remain unchanged.

## Installation

Update the custom integration through HACS / Marketplace, restart Home Assistant,
and open the **Availability** sidebar panel. There is no separate dashboard
YAML or manual frontend resource to install. The panel is read-only and
accessible to HA administrators only.
