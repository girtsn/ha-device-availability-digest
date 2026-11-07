# Device Availability Digest v0.3.0 — integrated diagnostics dashboard

## Integration-managed dashboard

- New **Availability** sidebar panel following the versioned loader, Home Assistant
  theme colors, responsive cards and tabbed layout used by the tado X / Tylö
  Sauna integrations. No manual dashboard YAML, HACS resource registration,
  or `configuration.yaml` changes are required.
- **Home Presence** tab: shared `sensor.home_presence`, current HA People
  locations and originating tracker IDs, trusted positive Home sources,
  Home/Away/Unknown change events and detailed source evidence changes.
- **Device availability** tab: current confirmed outages, pending devices,
  short connection interruptions (no email), OFFLINE/RECOVERED incidents,
  and successful immediate/summary emails.
- Filter periods (24 h / 7 / 30 / 90 days), daily activity chart,
  search by entity/device/MAC/IP/SSID, expandable diagnostic event details.

## Persistent, privacy-conscious event history

- New private HA storage `.storage/device_availability_digest_history` keeps
  up to 90 days or 5,000 diagnostic events across restarts.
- Records contributing entity IDs, Person `source` tracker IDs and
  available network identifiers; **does not store GPS coordinates**.
- New administrator-only, read-only `device_availability_digest/history`
  WebSocket endpoint. The panel is restricted to administrators.
- No historical backfill: history begins after installation.

## Compatibility

- Existing five-minute offline confirmation, twenty-minute email digest,
  exclusions and persisted outage state remain unchanged.
- Generic presence logic continues to use Home Assistant's `person.*` GPS
  zone state and any trusted entity labeled **Home Presence**.
- A labeled Wi-Fi client going offline never, by itself, causes Away;
  unknown or missing Person locations block Away.
- The integration **does not** operate Tado, lighting, ventilation or other
  consumers. Those remain independent automations in private HA configuration.
- Home Assistant restart required to load updated Python and register the
  dashboard; no new third-party dependencies.
