# Device Availability Digest

Home Assistant integration that detects device disconnections, confirms them after a delay, and prevents a flood of individual notifications during network updates.

**Status: early HACS/Marketplace custom-repository release (v0.1.0).** The restart-safe state machine has automated tests; the complete integration still needs an end-to-end test on a live Home Assistant instance before critical use.

## Features

- **Five-minute confirmation (configurable):** skip brief offline glitches.
- **20-minute fixed digest window (configurable):** first confirmed outage generates a single immediate alert; subsequent confirmed outages and recoveries go into one summary email at the deadline.
- **Persistent restart-safe state:** pending outages, active outages, the window deadline and queued events are stored in Home Assistant's local `.storage` through atomic writes.
- **Recovery-only summaries:** when an outage recovers after its original summary, include the recovery in the next digest; do not send a misleading individual recovery email.
- **Auto-select one representative entity per registered device** and prefer standard `binary_sensor` entities whose `device_class` is `connectivity`. Supports manual connectivity overrides.
- **Monitor multiple cloud/API connection statuses on the same device:** API sensors with `connectivity_scope` equal to `main_api` or `settings_api`, plus `tado_home_id`, are tracked independently.
- **TV filtering:** TV-like devices are ignored by default to avoid normal power-off notifications; adjustable in Options.
- **User-selectable `notify.*` target**, exclusions, periods and connectivity overrides through the Home Assistant UI.
- **Optional private profile import** to prefill your exact site-specific entity IDs without publishing them.

No MQTT broker, external cloud backend, tokens, or GitHub access is required at runtime.

## Installation (custom repository)

This repository is public but is **not** part of the default catalogue.

1. In Home Assistant 2026.11+, use **Settings → Apps & integrations → Marketplace** (older versions: **HACS**). Add the repository URL `https://github.com/girtsn/ha-device-availability-digest` as a custom **Integration** repository.
2. Install **Device Availability Digest**, then restart Home Assistant so its Python integration loads.
3. **Disable your older device offline/recovered email automations before enabling this integration** to prevent duplicate alerts.
4. Go to **Settings → Devices & services → Add integration → Device Availability Digest**.
5. Confirm the suggested `notify.*` entity and the default five-minute and 20-minute settings. Change advanced options later via **Configure**.

If the repository does not appear in the custom repository list on your HA version, use manual installation: copy `custom_components/device_availability_digest/` to `/config/custom_components/device_availability_digest/`, restart HA, then add the integration from Devices & services.

No `configuration.yaml` entry is required or supported by this UI-based integration.

## No-hand-entry private configuration

During the initial config flow, the integration:
- Suggests an available `notify.*` entity, preferring names containing `email`.
- Prefills common Foscam-type switch proxies as exclusions if those entities exist.
- Detects typical TV devices and excludes them automatically, based on device registry metadata and a media-player entity.
- Prefers standard binary connectivity sensors when selecting a representative entity.
- Recognizes both tado API diagnostics through their attributes, without relying on exact entity IDs.

For precise per-home overrides, optionally put a JSON file named `/config/device_availability_digest_profile.json` on the HA system **before adding the integration**. It will prefill the config-flow data automatically without publishing the private IDs. Example:

```json
{
  "notify_entity": "notify.my_email",
  "offline_minutes": 5,
  "window_minutes": 20,
  "auto_exclude_tvs": true,
  "excluded_entities": ["switch.example_camera_proxy"],
  "excluded_device_entities": ["media_player.example_tv"],
  "connectivity_entities": ["binary_sensor.example_controller_online"]
}
```

`excluded_device_entities` are *anchors*: the integration resolves each named entity's registered device and ignores the whole device. The other two lists operate at entity level. The profile is only read when the config flow is first opened. To edit settings later, use the integration's **Configure** button.

**Do not publish household profile files or Home Assistant's `.storage` directory**. The integration never fetches private profiles from GitHub, even if the code was installed with HACS.

## How the emails work

For an outage confirmed at **12:05** after the device began failing at 12:00:
- **12:05** — first email: `[HASS] OFFLINE: device name`.
- **12:05–12:25** — additional offline/recovered events get recorded, not separately emailed.
- **12:25** — one email: `[HASS] AVAILABILITY SUMMARY`, listing event times, areas, entity IDs and remaining unresolved incidents.

The periodic check runs roughly every 30 seconds. A device that went offline and recovered in under the confirmation delay produces neither an OFFLINE nor a RECOVERED email.

## Restart persistence and limitations

State is saved via the Home Assistant storage API at `/config/.storage/device_availability_digest`. Keep the same persistent `/config` volume when replacing or restarting the container.

After a restart the integration restores the batch deadline, confirmed incidents and pending five-minute timers, then reconciles them against live entity states. Incidents occurring entirely while HA was stopped cannot be reconstructed exactly; initial observations after startup use the startup timestamp. Notifications require a functioning `notify.*` provider. A crash after sending an email but before persisting the sent flag can produce a duplicate (best-effort, not exactly-once delivery). Very large events may produce long emails; notification services can impose message-length limits.

Do not run the old YAML implementation at the same time; its delayed triggers/waits do not share this integration's persistent state.

## Validation

GitHub Actions runs Python syntax checks, unit tests, HACS/Marketplace validation, and hassfest on changes. Locally:

```bash
python -m compileall -q custom_components tests
python -m unittest discover -s tests -p 'test_*.py' -v
```

For a live smoke test: disconnect a non-critical sensor for more than five minutes, reconnect during the digest window, and verify one immediate email followed by one consolidated summary. Repeat with an HA restart while the batch remains open. Avoid testing by disconnecting safety-critical devices while active.

## Issues and license

Issues and feature requests: https://github.com/girtsn/ha-device-availability-digest/issues

MIT license.
