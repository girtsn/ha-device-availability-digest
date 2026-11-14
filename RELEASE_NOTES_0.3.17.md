# Device Availability Digest v0.3.17

- Ignore the redundant SBSE inverter grid-import measurement in stale alerts when a separate SHM2 import sensor exists, without creating any Home Assistant label.
- Exclude sleeping or powered-off Google Cast devices from offline alerts by default; an Options toggle can restore monitoring.
- Exclude the logical SMA Devices Plus plant device from offline alerts based on its `my_plant_*` source entities, while continuing to monitor the real inverter and SHM2.
- Retire previously active or queued incidents excluded by this policy on restart without generating a false recovery notification; preserve event history.
- Add regression coverage for optional SMA, Cast, Hue, and physical-device separation.
