# Device Availability Digest v0.3.9 — Retire invalid outages

## Fixed
- Reconcile persistent OFFLINE, PENDING and unsent digest records with currently monitored Home Assistant entities at startup, on entity/device registry changes and every availability timer tick.
- Silently drop incidents and queued events for deleted, disabled, excluded, unavailable-in-registry or no-longer-selected representative entities, without sending misleading recovery alerts or deleting historical diagnostics.
- Prevent UniFi `*_link_speed` and other diagnostic readings from being selected as device availability representatives, even if they were manually enabled. Explicit genuine cloud/connectivity sensors remain supported.
- Validate cached representatives before reusing them, and retire incidents when their Home Assistant state is removed.

## Compatibility
- Existing saved incidents for legitimately monitored offline devices remain unchanged.
- Retained 90-day history, Home Presence, stale-sensor monitoring and email settings are preserved.
- Update in HACS and restart Home Assistant. The Availability dashboard will then reflect the cleaned live outage set.
