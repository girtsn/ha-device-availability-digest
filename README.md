# Device Availability Digest

**v0.3.16 PM2.5 threshold accuracy:** The full configured observation window is now required before a new stuck-low flag. An observation age of 23.89 hours no longer qualifies for a 24-hour threshold; the monitor also retains a pre-window checkpoint to calculate exact coverage.\n\n**v0.3.15 eligibility reconciliation:** Previously flagged operational/configuration entities are now retired when the updated policy excludes them, without sending misleading recovery emails. Exclusions also inspect UI display names, not just entity IDs.\n\n**v0.3.14 stale-sensor corrections:** 24-hour stuck-low PM2.5 classification, real event sampling, filtering of configuration values, email delivery diagnostics and daily unresolved reminders.\n\n**v0.3.12 Home Presence mode timeline:** The Home Presence tab now displays
a categorical Home / Away / Unknown timeline directly below the current-status
tiles, using Home Assistant Recorder history (the same approach as the Tado X
Heating overview). It replaces the previous presence event-count histogram
without removing source diagnostics or incident history. The shared calendar
controls the selected period; gaps are left blank when Recorder has no data
rather than inferring a mode. The Device Availability and Stale Sensors charts
are unchanged. History availability depends on Recorder retention and inclusion
of `sensor.home_presence`.

**v0.3.11 self-contained PM2.5 detection:** Each physical PM2.5 sensor is monitored **independently** for a prolonged (about 48h) run of near-zero 0–2 µg/m³ readings. Minor 0↔1↔2 fluctuations do not hide the potential failure mode, and no other sensor is referenced. This is advisory **SUSPECT**, never a confirmed offline state.

**v0.3.9 monitoring cleanup:** Current OFFLINE/PENDING records and queued alerts are automatically reconciled against the live HA entity/device registry after startup, on registry changes and during the 30-second monitoring tick. Deleted, disabled, excluded, removed and no-longer-representative entities are retired without false recovery emails; historical events remain available. UniFi `*_link_speed` readings and ordinary diagnostic entities are not used as availability proxies (explicit real connectivity sensors remain eligible).


Home Assistant integration that detects device disconnections, confirms them after a delay, and prevents a flood of individual notifications during network updates.

**Status: v0.3.16 HACS/Marketplace custom-repository release.** The restart-safe state machine has automated tests; the complete integration still needs an end-to-end test on a live Home Assistant instance before critical use.

## Features

- **Five-minute confirmation (configurable):** skip brief offline glitches.
- **20-minute fixed digest window (configurable):** first confirmed outage generates a single immediate alert; subsequent confirmed outages and recoveries go into one summary email at the deadline.
- **Persistent restart-safe state:** pending outages, active outages, the window deadline and queued events are stored in Home Assistant's local `.storage` through atomic writes.
- **Recovery-only summaries:** when an outage recovers after its original summary, include the recovery in the next digest; do not send a misleading individual recovery email.
- **Auto-select one representative entity per registered device** and prefer standard `binary_sensor` entities whose `device_class` is `connectivity`. Supports manual connectivity overrides.
- **Monitor multiple cloud/API connection statuses on the same device:** API sensors with `connectivity_scope` equal to `main_api` or `settings_api`, plus `tado_home_id`, are tracked independently.
- **TV filtering:** TV-like devices are ignored by default to avoid normal power-off notifications; adjustable in Options.
- **User-selectable `notify.*` target, email subject prefix**, exclusions, periods and connectivity overrides through the Home Assistant UI.
- **Optional private profile import** to prefill your exact site-specific entity IDs without publishing them.

No MQTT broker, external cloud backend, tokens, or GitHub access is required at runtime.

## Integration-managed diagnostic dashboard (v0.3.1)

**Availability** appears in the Home Assistant sidebar automatically after
updating/restarting this integration, using the same integration-managed,
versioned sidebar-panel pattern as the Tado X and Sauna dashboards.
No manual Lovelace cards, resource registration or configuration.yaml entries
are necessary. The panel is **administrator-only** because it displays
household presence and local network identifiers.

The dashboard has three tabs:

- **Home Presence:** current `home / away / unknown` state, a Recorder-backed **mode timeline** near the top, **all** tracked
  `person.*` GPS sources and all entity-level **Home Presence**-labeled
  Wi-Fi/occupancy sources, including currently `not_home` or `unavailable`
  devices. Each source shows its current state, **Last update** and
  **Last seen Home** timestamps. GPS source timestamps are displayed separately
  from Person state when available. Active Home sources still determine
  occupancy, while timestamps help identify stale trackers. The event log
  preserves source changes and MAC/IP/SSID **only when HA provides them**;
  latitude/longitude are never copied into the diagnostic history.
- **Stale sensors:** current report-age coverage of numeric measurements, including monitored healthy readings, pending unknown/unavailable readings, confirmed missing reports, opt-in suspected frozen values and automatic self-only near-zero PM2.5 anomalies. Search by entity/room and inspect the last report time, unchanged-value time, rule threshold and reason. Includes a 90-day transition and email history.
- **Device availability:** current confirmed outages and pending
  disconnections, searchable history of pending, short recoveries (no email),
  confirmed OFFLINE and RECOVERED incidents, plus successful immediate-email
  and digest-summary notifications. Cloud/API scopes and failure reasons
  remain visible in each relevant incident.

Both views share **the same Tado X / Tylö date-range calendar**, including
Today, Yesterday, This Week/Month/Quarter/Year, Last 7/30/365 days,
Last 12 months / 3 years, custom calendar ranges and previous/next arrows.
The history still retains only the last **90 days**, so longer or older
selections do not invent historical records. Charts switch between hourly,
daily, weekly and monthly summaries as appropriate.

A **mobile hamburger button** opens Home Assistant's navigation drawer, as
on the Tado X / Tylö managed panels. Search supports entity ID, device
name, MAC/IP/SSID, with click-to-expand diagnostics. **Actual state
transitions** are distinguished from **source metadata updates** such as
an IP/MAC/source change while the reported presence state remains home;
legacy same-state entries also display as details, not transitions.

They use Home Assistant colors/theme, responsive cards and a versioned
sidebar loader. Dashboard data is **read-only**: opening it does not change
notification settings, geofencing, heating or device network access.

Diagnostic events are stored in a separate **private Home Assistant storage**
file, retained for **90 days, maximum 5,000 records**, across HA restarts.
Old email incidents are **not backfilled** into this history; it starts from
installation of this version. Neither source code nor public GitHub contains
the user's event data. GPS coordinates are **never copied into the diagnostic
log**; only HA state names (e.g. `home`/`not_home`/`work`) and source
identifiers are logged. Home Assistant still stores its usual location data
separately according to the user's Recorder configuration.

The read API `device_availability_digest/history` is available only to
authenticated **administrators**. When the integration is removed, its
sidebar panel is removed too; disabling it does not erase the separately
persisted diagnostic history.


## Stale sensor measurements (v0.3.14)

The separate restart-safe monitor checks physical numeric measurements every
15 minutes. It excludes setpoints, programme progress, operational controls,
standby status, SMA power limits, totals, diagnostics and nonphysical services.
Exclusions inspect both entity IDs and HA-visible names, so renamed entities
still match. Previously flagged excluded entities are immediately retired on
reconciliation without generating false recovery emails; pending notifications
about those now-excluded entities are silently removed.
If an unusual entity really measures a physical quantity, add the entity-level
`stale_monitor_include` label. To exclude any other entity, use
`stale_monitor_ignore` (always takes precedence).

**Signals and classification**

- `STALE / no_report`: no Home Assistant report within the applicable timeout.
  Some integrations publish only state changes, so this does not by itself
  prove a physical failure.
- `STALE / unknown` or `unavailable`: a physical measurement has entered an
  invalid state beyond its grace period.
- `STALE / pm25_stuck_low`: 24 hours (configurable 12–72h) of unusually low, nearly static PM2.5.
  State-change events are captured between 15-minute scans. Zero-to-one
  readings dominate at least 70% of the observation period, while occasional
  readings of 2–5 µg/m³ are tolerated. Only a sustained rise **above 5 µg/m³
  for at least 45 minutes** clears an existing stuck-low classification;
  a single spike cannot clear it. The observation window, high threshold and sustained recovery duration are configurable in integration Options (defaults 24h, 5 µg/m³, 45m). A sensor is assessed on its own readings,
  not by comparison with other devices or rooms. Genuine very clean air
  may still trigger this heuristic: STALE means likely stale *measurement*,
  not verified hardware failure.
- `SUSPECT / unchanged_value`: opt-in rule for continuously reported but
  unchanged readings using `stale_monitor_watch_value`.

Other entity-level labels: `stale_monitor_fast` (3h missing-report timeout),
`stale_monitor_slow` (168h), `stale_monitor_include`,
`stale_monitor_ignore` and `stale_monitor_watch_value`. Default missing
report thresholds are **12h air, 48h ambient, 72h electrical, 168h other**.
Unknown/unavailable state grace is at most 12h for air or 24h for others.

**Notification behaviour:** send queued new flags, reclassifications and
clearances at **08:00 and 20:00 Home Assistant local time** to the independent
`stale_notify_entity` (configured in integration Options).
`stale_daily_reminder_enabled` (default on) also sends a daily 08:00 summary
while any flags remain unresolved even if no changes occurred. Failed notify
calls do not acknowledge the queued events, and are recorded as EMAIL_FAILED
with the error and target. The dashboard shows last attempted delivery,
target, result, error and queue depth. A successful HA notify service call
does *not* guarantee actual delivery to the mailbox.

The dashboard presents actual time since HA last reported, time since the
value changed, PM2.5 observation window and the separate reason-specific
threshold. Storage is private and restart-persistent. Diagnostic history is
retained for 90 days (up to 5,000 events).

**Upgrading:** restart HA, check the stale-sensor `notify.*` recipient and
the reminder option at **Settings → Devices & services → Device Availability
Digest → Configure**. Disable the former YAML stale-sensor automation if
still active. Review **Availability → Stale sensors → All monitored** and
apply explicit include/ignore labels as needed. New installations need about
24 hours of PM2.5 observation; saved older PM2.5 samples are reused.

## Optional SMA inverter-side grid-import sensor

With an SBSE inverter and a separate Sunny Home Manager 2, the
`sensor.sbse*_metering_power_absorbed` inverter-side channel is redundant
when `sensor.shm2_em_metering_power_absorbed` exists. The stale monitor
therefore ignores that SBSE channel automatically. The SHM2 meter remains
monitored. No Home Assistant label is created or required. Assign
`stale_monitor_include` if you deliberately want to monitor it.
This never disables the entity or changes energy statistics.

## Tracker timestamps (v0.3.7)

The **Home Presence → Current evidence** section lists both **People / Companion
App GPS** and **all Home Presence-labeled Wi-Fi sources**, even when they are
disconnected or no longer confirming Home.

- **Last update:** The actual last HA state-report timestamp
  (`last_reported`, falling back to `last_updated` or the state-change time
  in older HA frontend versions). For People, the Companion App GPS tracker
  is preferred over the aggregate `person.*` entity when its source is
  known. This is **not necessarily a fresh GPS fix**: it means HA received or
  updated that entity's state.
- **Last seen Home:** The latest timestamp at which the Person or labeled
  source reported Home (or `on` for labeled occupancy/manual overrides).
  Persisted in the integration's **private** diagnostic storage across
  Home Assistant restarts, even when the source later reports Away.
  It is recorded using the source's actual HA report/update timestamp, not
  the time somebody opens the dashboard or the 30-second check time.
  No GPS coordinates are saved.
- **Unknown (`—`):** No positive Home report has been observed by this
  integration yet, for example when a device is already Away on the first
  installation of v0.3.7. Earlier Home timestamps are not invented or
  reconstructed from missing historical data.

This is **diagnostic only**: timestamps do not alter the 20-minute absence
qualification or override presence decisions. The timestamp cache is
bounded to 256 source IDs and is accessible only through the existing
administrator-only diagnostics endpoint. Legacy event retention remains
90 days / 5,000 events.

## Generic Home Presence (v0.2.0+)

The integration also exposes **`sensor.home_presence`**, a reusable,
read-only, vendor-neutral household presence state:

| State | Meaning |
| --- | --- |
| `home` | A Home Assistant `person.*` is `home`, or a trusted labeled source positively reports a person at home |
| `away` | No Person or trusted labeled Wi-Fi/occupancy source has confirmed Home for **20 continuous minutes**, with all Persons either Away, at other zones or Unknown/Unavailable |
| `unknown` | No positive Home evidence yet, but the new **20-minute no-Home confirmation** has not elapsed, or no Person entities are configured |

Presence detection is **independent of the availability digest notification logic**.
It does not send messages, switch Tado, or control any other devices.
Use `sensor.home_presence` in your own automations.

### Configure the sources

1. In **Settings → People**, associate each household member with their
   Home Assistant Companion App **GPS** tracker. Enable background location
   reporting and reliable connectivity away from the home Wi-Fi. The custom
   integration reads the resulting `person.*` states; it does *not* perform
   smartphone GPS tracking itself.
2. In **Settings → Areas, labels & zones → Labels**, create **Home Presence**.
   Add that label to trusted **entity-level** positive presence sources, e.g.:
   - `device_tracker` -> state `home` (UniFi Wi-Fi client, Bluetooth tracker)
   - `binary_sensor` -> state `on` (reliable human occupancy)
   - `input_boolean` -> state `on` (intentional manual guest override)
   - `sensor` -> state `home` (another occupancy source)
3. Add labels only to reliable signals of **human** presence. Do not label
   generic online devices, Wi-Fi access points, motion sensors not reliable
   for whole-house occupancy, UniFi Blocked switches, or orphaned MAC clients.
4. Verify `sensor.home_presence` in **Developer Tools → States**. Its
   attributes list `tracked_people` and `active_home_evidence`.
   Existing installations may have chosen another entity ID if
   `sensor.home_presence` already exists; inspect the integration's entities.

**Revised Away rule (v0.3.6):** As soon as any Person is `home` or any
trusted source labeled **Home Presence** positively reports Home, the
household is **Home**, regardless of the other phones' states. If all
People are `not_home`, at other zones, `unknown` or `unavailable`,
and **none** of the labeled Wi-Fi/occupancy sources confirms Home,
the household becomes **Away after 20 continuous minutes without
positive Home evidence**. A phone in power saving mode or temporarily
unable to provide GPS updates can no longer block Away indefinitely.
Wi-Fi disconnection on its own does not trigger an *instant* Away.

The 20-minute no-Home timer starts when the integration first observes
no positive Home source, resets whenever Home is confirmed, and starts
fresh after a Home Assistant integration restart. The sensor refreshes
every 30 seconds as well as on relevant state changes. Attributes
`absence_candidate_since`, `unknown_or_unavailable_people`, and
`configured_home_sources` are exposed for troubleshooting.

**Safety trade-off:** If all phone GPS signals are unknown while trusted
Wi-Fi sensors are offline, incorrectly configured, or unavailable for
20 minutes, the household can now be reported Away **even if someone is
physically home**. Use this for heating setback and other reversible
comfort automations, not alarms, locks, or other safety-critical actions.
Configure a reliable Wi-Fi tracker for each household phone and, if
needed, a reliable, explicitly labeled manual Home override.
All `person.*` entities still participate; exclude extraneous Persons
from Home Assistant's household configuration.

### Example consumer automation

```yaml
alias: Example - react to confirmed Home Presence
triggers:
  - trigger: state
    entity_id: sensor.home_presence
    to: home
actions:
  - action: logbook.log
    data:
      name: Home Presence
      message: Somebody arrived home
```

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
- Excludes Google Cast devices by default because sleeping or powered-off devices are normal; this is configurable in Options.
- Excludes SMA Devices Plus logical plant devices identified by source entities named `sensor.my_plant_*`, but continues to monitor physical inverters and SHM2 meters.
- Prefers standard binary connectivity sensors when selecting a representative entity.
- Recognizes both tado API diagnostics through their attributes, without relying on exact entity IDs.

For precise per-home overrides, optionally put a JSON file named `/config/device_availability_digest_profile.json` on the HA system **before adding the integration**. It will prefill the config-flow data automatically without publishing the private IDs. Example:

```json
{
  "notify_entity": "notify.my_email",
  "offline_minutes": 5,
  "window_minutes": 20,
  "auto_exclude_tvs": true,
  "auto_exclude_cast": true,
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

## Subject prefixes and tagged releases

The initial setup and **Configure / Options** UI provide an **Email subject prefix**. The default is `[HASS]`; for example, `[House]` produces `[House] OFFLINE: Device` and `[House] AVAILABILITY SUMMARY: ...`. Leave the prefix blank for unprefixed subjects. A local private profile can set `"email_subject_prefix": "[House]"` to prefill the value.

The repository uses the same GitHub Release model as Renson Sense and Tylö Sauna: bump the `version` in `custom_components/device_availability_digest/manifest.json`, optionally add `RELEASE_NOTES_<version>.md`, and push to `main`. After successful CI validation of **the current main commit**, the workflow publishes the matching `v<version>` tag and GitHub Release for HACS; it skips versions already released and stale workflow runs. No ZIP asset is required.

One-time GitHub metadata: set repository topics such as `home-assistant`, `hacs`, `home-assistant-custom-component`, and `device-monitoring` in the repository's **About** section. The HACS validation workflow temporarily ignores the repository-topic check until topics are added; other checks remain active.

## Logical rooms and service-device monitoring (v0.3.4)

Availability Digest monitors **registered physical devices**, not virtual service-type Home Assistant device-registry entries (for example, Hue Rooms/Zones or other logical groups). These service entries can have misleading `binary_sensor.*_connectivity` states and must not be counted as independent device outages. On startup, v0.3.4 also retires persisted virtual-service incidents without emitting artificial recovery emails; prior historical records are not rewritten.

The expanded details for current/pending items include the **source integration** (entity-registry platform), to help identify whether a sensor comes from Hue, MQTT, Ping, another integration or a custom provider. A value of `scope: device` only indicates a default monitoring scope; it never proves the item is a physical device.

Real physical lights, plugs, sensors, thermostats and local/cloud API status signals remain monitored according to the existing policies. **Important:** not every integration registers synthetic room/group endpoints as service-type devices. If an unwanted room sensor still appears, open its entity details in Home Assistant and inspect its integration and device model before making a targeted exclusion. An `unknown` connectivity state can still cause noise for physical devices; this is a separate signal-quality issue to evaluate after identifying the provider.

## tado logical heating-zone exclusion (v0.3.5)

The tado X custom integration registers its **logical room/Zone** entries as normal Home Assistant devices with manufacturer `Tado` and model `Zone`, not `entry_type: service`. They contain room `binary_sensor.*_connectivity` entities that can create misleading bulk OFFLINE incidents. Device Availability Digest now ignores those zone entries regardless of entity name. It also removes previously persisted zone incidents from pending, active and unfinished email batches when the upgraded integration starts; saved diagnostic-history events are retained.

Actual tado thermostat hardware remains eligible for normal monitoring, and the independent tado X `main_api` and `settings_api` connection health sensors remain monitored because they are attached to the Tado `Home` device. The filter uses registry manufacturer/model metadata, not arbitrary room-name patterns.

Update through HACS to v0.3.5 and restart Home Assistant. If a tado room still appears, expand the incident and check the device-registry manufacturer and model; report the entity and metadata so an additional logical variant can be recognized safely.
