"""Pure Python regression tests for generic Home Presence."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

# Load the pure model without importing the Home Assistant-dependent package.
MODEL = Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest" / "presence.py"
spec = spec_from_file_location("home_presence_model", MODEL)
module = module_from_spec(spec)
spec.loader.exec_module(module)
decide_presence = module.decide_presence

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)


class PresenceTests(unittest.TestCase):
    def test_wifi_home_is_sufficient(self):
        self.assertEqual(decide_presence([], ["device_tracker.phone"], NOW), "home")

    def test_wifi_disconnect_is_not_sufficient(self):
        self.assertEqual(decide_presence([], [], NOW), "unknown")

    def test_one_person_home_overrides_other_away(self):
        self.assertEqual(decide_presence([("home", NOW), ("not_home", NOW - timedelta(hours=2))], [], NOW), "home")

    def test_all_people_confirm_away(self):
        self.assertEqual(decide_presence([("not_home", NOW - timedelta(minutes=21)), ("work", NOW - timedelta(hours=1))], [], NOW), "away")

    def test_grace_period(self):
        self.assertEqual(decide_presence([("not_home", NOW - timedelta(minutes=19))], [], NOW), "unknown")

    def test_unknown_blocks_away(self):
        self.assertEqual(decide_presence([("unavailable", NOW - timedelta(days=1)), ("not_home", NOW - timedelta(hours=1))], [], NOW), "unknown")

    def test_labeled_source_overrides_confirmed_away(self):
        self.assertEqual(decide_presence([("not_home", NOW - timedelta(hours=1))], ["device_tracker.phone"], NOW), "home")

    def test_future_clock_skew_blocks_away(self):
        self.assertEqual(decide_presence([("not_home", NOW + timedelta(seconds=2))], [], NOW), "unknown")


if __name__ == "__main__":
    unittest.main()
