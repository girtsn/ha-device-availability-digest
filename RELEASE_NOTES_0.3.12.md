## Device Availability Digest v0.3.12

### Home Presence mode history

- Added a Home / Away / Unknown timeline under the Home Presence summary tiles, in the same categorical style as the Tado X Heating dashboard.
- Uses Home Assistant Recorder history for `sensor.home_presence` and follows the dashboard's shared date-range picker, including calendar ranges and past periods.
- Shows the recorded duration of each mode, not the number of diagnostic events. Each segment has an exact local-time tooltip; unknown/unavailable states are distinguished from unrecorded gaps.
- Removed the previous Home Presence event-count histogram while retaining the detailed presence-source and state-transition log.
- Retained existing Device Availability and Stale Sensors timelines, device monitoring, email digests and stale-sensor logic unchanged.

**Upgrade:** Update the custom repository via HACS and restart Home Assistant. The managed panel automatically uses the versioned frontend asset. Recorder must include `sensor.home_presence` for mode-history data; neither earlier states nor periods beyond Recorder retention are reconstructed. All charts remain read-only.
