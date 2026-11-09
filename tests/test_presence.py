"""Pure Python regression tests for generic household Home Presence."""
from datetime import datetime, timedelta, timezone
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import unittest

MODEL = Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest" / "presence.py"
spec = spec_from_file_location("home_presence_model", MODEL)
module = module_from_spec(spec)
spec.loader.exec_module(module)
decide_presence = module.decide_presence

NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(minutes=21)
RECENT = NOW - timedelta(minutes=19)


class PresenceTests(unittest.TestCase):
    def decide(self, people, positive=(), since=OLD, now=NOW):
        return decide_presence(people, positive, now, absence_since=since)

    def test_wifi_home_always_wins(self):
        self.assertEqual(self.decide([], ["device_tracker.wifi_phone"]), "home")
        self.assertEqual(self.decide([("unknown", None)], ["device_tracker.wifi_phone"]), "home")

    def test_wifi_disconnect_alone_with_no_people_is_not_away(self):
        self.assertEqual(self.decide([], [], since=OLD), "unknown")

    def test_one_person_home_overrides_other_away_or_unknown(self):
        people = [("home", NOW), ("not_home", OLD), ("unknown", None)]
        self.assertEqual(self.decide(people), "home")

    def test_all_people_confirmed_outside_after_delay(self):
        people = [("not_home", OLD), ("work", NOW - timedelta(hours=1))]
        self.assertEqual(self.decide(people), "away")

    def test_unknown_phone_does_not_veto_away(self):
        people = [("unavailable", NOW), ("not_home", OLD), ("unknown", None)]
        self.assertEqual(self.decide(people), "away")

    def test_all_unknown_after_no_home_confirmation_period(self):
        people = [("unknown", None), ("unavailable", None)]
        self.assertEqual(self.decide(people), "away")

    def test_no_wifi_home_signal_and_away_plus_unknown_people(self):
        people = [("not_home", NOW), ("unknown", NOW)]
        self.assertEqual(self.decide(people, positive=[]), "away")

    def test_grace_period_prevents_premature_away(self):
        people = [("not_home", OLD), ("unknown", None)]
        self.assertEqual(self.decide(people, since=RECENT), "unknown")
        self.assertEqual(self.decide(people, since=NOW), "unknown")
        self.assertEqual(self.decide(people, since=NOW - timedelta(minutes=20)), "away")

    def test_missing_or_future_absence_start_blocks_away(self):
        people = [("not_home", OLD), ("unknown", None)]
        self.assertEqual(self.decide(people, since=None), "unknown")
        self.assertEqual(self.decide(people, since=NOW + timedelta(seconds=2)), "unknown")

    def test_wifi_positive_wins_even_after_away_confirmed(self):
        people = [("work", OLD), ("unknown", None)]
        self.assertEqual(self.decide(people, positive=["device_tracker.wifi_home"]), "home")

    def test_reboot_or_initialization_requires_fresh_20_minute_period(self):
        self.assertEqual(self.decide([("not_home", OLD)], since=NOW), "unknown")
        self.assertEqual(self.decide([("not_home", OLD)], since=OLD), "away")

    def test_custom_delay(self):
        self.assertEqual(decide_presence(
            [("unknown", None)], [], NOW, timedelta(minutes=30),
            absence_since=OLD,
        ), "unknown")


if __name__ == "__main__":
    unittest.main()
