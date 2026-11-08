# Device Availability Digest v0.3.5 — Exclude tado logical zones

Fix the mass room-disconnection false positives observed with tado X.

- Exclude logical tado **Zone** device-registry entries (manufacturer `Tado`, model `Zone`) even though tado registers them as regular device entries instead of `entry_type: service`.
- Stop treating their `binary_sensor.*_connectivity` states and room climate entities as independent device-availability incidents.
- On restart, silently remove previously persisted tado Zone incidents from active/pending state and uncompleted digest batches, without fabricating RECOVERED emails. Existing diagnostic history stays intact.
- **Preserve** physical tado thermostats (hardware models), both `main_api` and `settings_api` cloud connection monitors under tado Home, and other non-tado devices including the 1fl towel dryer.
- Add regression tests for tado Home vs Zone vs physical device classification and retention of active API incidents.

**Migration:** Install v0.3.5 through HACS and restart Home Assistant. Reopen the Availability panel to verify that tado room names no longer appear under current outages. Genuine device outages and diagnostic history are not erased. Notification behavior remains five-minute confirmation followed by twenty-minute digest.

This filtering is separate from investigation of Tuya Local disconnection detection and notification delivery.
