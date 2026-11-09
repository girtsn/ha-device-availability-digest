# Device Availability Digest v0.3.7 — Last update and Last seen Home

## Improved Home Presence evidence

The **Availability & Home Presence → Home Presence → Current evidence** card
now lists **all configured sources**, not only those currently reporting Home:

- **People / Companion App GPS:** Person state, originating GPS tracker (when
  available), the latest HA report/update timestamp of that GPS tracker, and
  the last time the Person was observed Home.
- **Home Presence-labeled Wi-Fi and manual override sources:** Current state,
  optional IP/MAC/SSID from HA, **Last update**, and **Last seen Home**.
  Disconnected (`not_home`) and temporarily unavailable trackers remain visible.
- Dates display in the Home Assistant browser's local timezone, with a dash
  when a source has no known report or Home observation.

## Reliable timestamps and privacy

Last update uses HA's actual `last_reported` timestamp, falling back to
`last_updated` or `last_changed` in older HA clients. It does **not**
invent a heartbeat and is not necessarily proof of a fresh GPS fix.

Last seen Home is maintained from genuine positive Home state reports and
stored in the existing **private diagnostic Store** as a bounded timestamp
map. It survives restart, loss of Wi-Fi and state changes to `unknown` /
`not_home`. The final positive report is captured before a Home -> Away
transition. This version does **not** reconstruct Home times before it was
installed: previously unseen sources display a dash until they report Home.

No GPS coordinates or authentication secrets are stored. Only authenticated
administrators can access the diagnostic API. No new remote/cloud calls.

## Compatibility

The Away logic introduced in v0.3.6 stays unchanged. No changes to device
availability emails, the Home Presence consumer automation, heating modes,
other sensors or current Home Assistant entity IDs.

Tests cover Home state semantics, UTC normalization, out-of-order reports,
and the browser dashboard showing disconnected sources and source timestamps.
