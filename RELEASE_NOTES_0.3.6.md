# Device Availability Digest v0.3.6 — Home Presence tolerates sleeping phones

## Household Home/Away decision

- A Person explicitly reporting **Home** or any trusted, labeled **Home Presence** source reporting Home continues to immediately establish `sensor.home_presence = home`.
- When **no** Person and **no** trusted Wi-Fi/occupancy signal confirms Home, start a continuous **20-minute absence confirmation timer**. After it elapses, report `away` even if one or more Person entities are `unknown` or `unavailable`. A sleeping/disconnected Companion App can no longer indefinitely block Away.
- `unknown` is reported while the 20-minute period is in progress or if there are no Person entities configured. The timer resets after any positive Home signal, and starts fresh when the integration restarts to avoid spurious immediate Away transitions.
- The existing refresh-on-state-change and 30-second periodic evaluation complete the transition without polling GPS or Wi-Fi directly.
- New diagnostic attributes: `absence_candidate_since`, `unknown_or_unavailable_people`, and `configured_home_sources`. The availability dashboard still shows the contributing Person states and Home evidence.

## Safety trade-off

If all GPS sources are unknown and every Wi-Fi confirmation is absent (including due to outages), the household can now be reported Away after 20 minutes even when somebody is physically home. Use for reversible comfort/heating controls, **not** locks, alarms or other security/safety-critical decisions. Ensure reliable, explicitly labeled Wi-Fi presence sources and an optional manual Home override for guests.

## Compatibility and deployment

No Tado X integration or household application automation changes are required. The existing generic Home Presence controller already follows `sensor.home_presence`. No data history, entity IDs, availability-digest email rules or user configuration are modified. The change takes effect after updating this HACS integration and restarting Home Assistant.

Python unit tests cover Home priority, all Persons unknown, mixed Away/unknown, recovery of Home evidence, cold starts, timing and clock skew.
