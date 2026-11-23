# Device Availability Digest 0.3.18 — Correct calendar dates

- Availability history date-range controls now follow the **Home Assistant configured timezone**, not the browser timezone.
- Correct yesterday and individual-day selection across daylight-saving changes.
- Select exactly one day by tapping the date and pressing Select; a second tap extends the range.
- Preserve existing data collection, state machine, reports and alerting.
- Add regression tests for timezone, DST, and manual day selection.
