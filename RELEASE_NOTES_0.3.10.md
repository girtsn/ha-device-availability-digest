# Device Availability Digest v0.3.10 — Detect suspicious low-variation PM2.5

## Added
- The Stale sensors monitor now catches a plausible PM2.5 sensor failure that a fresh state report or an occasional 0→1→2 change could otherwise conceal.
- Every 15 minutes, maintain a rolling 24-hour history of **eligible physical PM2.5** sensors in the existing private restart-safe Store.
- Flag a measurement as **SUSPECT** (not OFFLINE or confirmed STALE) when it remains in **0–2 µg/m³** and another active PM2.5 sensor shows a 24-hour median of at least **6 µg/m³** with a range of at least **4 µg/m³**. Require at least 20 samples over 22 hours for both sensors.
- Respect existing measurement selection and `stale_monitor_ignore`; do not flag a low-reading sensor without an active, varying peer. Clear the suspicion when the evidence no longer holds.
- Display these findings under **Availability → Stale sensors**, and send delta-only notifications using the existing 08:00/20:00 digest.

## Compatibility
- Existing missing-report, unknown/unavailable and opt-in exact-frozen checks are preserved. Device availability alerts and Home Presence are unchanged.
- Historic Home Assistant Recorder readings are not imported. The 24-hour rolling comparison starts learning after the update and survives Home Assistant restarts.
- A filtered room can have genuinely low PM2.5. This is an advisory comparison, not confirmation of a faulty sensor.
- Update through HACS/Marketplace and restart Home Assistant.
