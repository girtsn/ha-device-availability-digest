# Device Availability Digest v0.1.1 — First HACS release

Initial tagged, versioned HACS release of Device Availability Digest.

- UI-configured device monitoring, automatically selecting representative connectivity entities
- Five-minute offline confirmation and 20-minute grouped offline/recovered digest
- One immediate alert for the first confirmed outage, then one end-of-window summary
- Durable pending outages, active incidents and summary deadline through Home Assistant restarts
- Independent monitoring of tado X API status sensors sharing one registered device
- Automatic TV filtering, plus user-defined device/entity exclusions
- Private optional local profile prefill: `/config/device_availability_digest_profile.json`
- Correct integration classification as a background service, not a Helper
- Local brand icon, automated Python state-machine tests and HACS/hassfest validation

**Installation:** In HACS, redownload/update the custom repository integration and restart Home Assistant. Disable any earlier "Device availability - dynamic email" automation to prevent duplicate alerts. If HACS previously installed this repository as an unversioned commit, use **Redownload** and explicitly select `v0.1.1` if an automatic update is not offered.

**Status:** Early release. End-to-end integration startup, persistence after actual Synology restarts and delivery through specific `notify.*` providers still require live testing. No changes to existing HA automations are made automatically by HACS.
