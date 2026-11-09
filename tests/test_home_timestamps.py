"""Pure tests for timestamp evidence used by Home Presence dashboard."""
from datetime import datetime, timezone, timedelta
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import unittest

MODEL = Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest" / "home_timestamps.py"
spec = spec_from_file_location("home_timestamp_model", MODEL)
model = module_from_spec(spec)
spec.loader.exec_module(model)

UTC = timezone.utc
NOW = datetime(2026, 11, 9, 9, 0, tzinfo=UTC)
EARLIER = datetime(2026, 11, 8, 13, 0, tzinfo=UTC)


class TimestampTests(unittest.TestCase):
    def test_last_reported_is_preferred_to_last_updated(self):
        obj = SimpleNamespace(last_reported=NOW, last_updated=EARLIER)
        self.assertEqual(model.reported_at(obj), NOW.isoformat())

    def test_old_home_assistant_can_fallback_to_last_updated(self):
        obj = SimpleNamespace(last_updated=NOW)
        self.assertEqual(model.reported_at(obj), NOW.isoformat())
        self.assertIsNone(model.reported_at(None))

    def test_reject_naive_timestamps(self):
        obj = SimpleNamespace(last_reported=datetime(2026, 11, 9, 9, 0))
        self.assertIsNone(model.reported_at(obj))

    def test_zones_and_binary_home_states(self):
        self.assertTrue(model.is_home_source("person.user", SimpleNamespace(state="home")))
        self.assertTrue(model.is_home_source("device_tracker.wifi", SimpleNamespace(state="home")))
        self.assertTrue(model.is_home_source("binary_sensor.occupancy", SimpleNamespace(state="on")))
        self.assertTrue(model.is_home_source("input_boolean.guest_home", SimpleNamespace(state="on")))
        self.assertFalse(model.is_home_source("device_tracker.wifi", SimpleNamespace(state="not_home")))
        self.assertFalse(model.is_home_source("person.user", SimpleNamespace(state="unknown")))
        self.assertFalse(model.is_home_source("sensor.temperature", SimpleNamespace(state="21")))
        self.assertFalse(model.is_home_source("switch.random", SimpleNamespace(state="on")))

    def test_home_timestamp_survives_away_and_out_of_order_updates(self):
        old = {"device_tracker.phone": EARLIER.isoformat()}
        updated = model.latest_timestamps(old, {"device_tracker.phone": NOW.isoformat()})
        self.assertEqual(updated["device_tracker.phone"], NOW.isoformat())
        stale = model.latest_timestamps(updated, {"device_tracker.phone": EARLIER.isoformat()})
        self.assertEqual(stale, updated)
        self.assertEqual(old["device_tracker.phone"], EARLIER.isoformat())

    def test_invalid_timestamps_do_not_corrupt_history(self):
        valid = {"person.user": NOW.isoformat()}
        merged = model.latest_timestamps(valid, {
            "person.user": "unknown",
            "device_tracker.other": "not a date",
            "device_tracker.naive": "2026-11-09T09:00:00",
        })
        self.assertEqual(merged, valid)

    def test_normalizes_time_zone_offsets(self):
        local = datetime(2026, 11, 9, 10, 0, tzinfo=timezone(timedelta(hours=1)))
        merged = model.latest_timestamps({}, {"person.user": local.isoformat()})
        self.assertEqual(merged["person.user"], NOW.isoformat())

if __name__ == "__main__":
    unittest.main()
