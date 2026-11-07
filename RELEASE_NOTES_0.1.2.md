# Device Availability Digest v0.1.2 — Configurable email subject prefix

- Add an **Email subject prefix** field to the initial setup and integration Options UI.
- Apply the configured prefix to both immediate **OFFLINE** subjects and **AVAILABILITY SUMMARY** subjects; alert content is unchanged.
- Default to `[HASS]` for existing installations (or customize it, e.g. `[House]` or leave blank).
- Read the setting from the optional local profile `/config/device_availability_digest_profile.json` when first configuring the integration.
- Existing installation options remain backward compatible; no need to remove/re-add the integration.
- Add unit tests covering custom, empty and whitespace-padded subject prefixes.
- Continue publishing releases automatically from the validated manifest version, with no special ZIP asset.

**Update:** Install v0.1.2 through HACS and restart Home Assistant. Then use **Settings → Devices & services → Device Availability Digest → Configure** to edit the subject prefix. Existing notification history and active digest state are preserved.
