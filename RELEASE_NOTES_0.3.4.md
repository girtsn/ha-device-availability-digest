# Device Availability Digest v0.3.4 — Ignore virtual rooms and identify source integrations

- Ignore Home Assistant device-registry **service-type devices**, including virtual rooms and zones, when selecting connectivity monitors.
- On integration restart, remove saved false outages for those virtual devices from pending/active incident state and unfinished digest batches **without generating fake recovery alerts**. Existing historical events remain as an audit record.
- Include each monitored entity's actual source integration in the dashboard's expanded current-outage/pending details and newly persisted availability history.
- Preserve the existing five-minute confirmation, 20-minute grouping, device-specific connectivity sensors, tado X API health monitoring, and persistent physical-device incidents.
- Add regression tests for service device classification, retiring stale virtual-room outages, and preserving real offline devices.

This release narrows scope using Home Assistant registry metadata, not device-name guesses. For any remaining false positives, inspect **Entity settings → Integration** and the expanded dashboard detail; a provider may register a logical item as a regular device instead of a service. The bare `scope: device` field is not authoritative physical-device metadata.

Update through HACS and restart Home Assistant to run the persistent-incident cleanup. Recheck the physical **1fl towel dryer** state separately; the scope fix does not prove the Tuya device's own connection status.
