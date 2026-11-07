"""Pure-state regression tests; do not require the Home Assistant package."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest"))
from model import AvailabilityState

T0 = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
D = timedelta(minutes=5)
W = timedelta(minutes=20)


def info(name="device", cloud=False):
    return {"name": name, "area": "test", "cloud": cloud, "scope": "device"}


class DigestTests(unittest.TestCase):
    def test_transient_outage_never_notified(self):
        s = AvailabilityState()
        self.assertTrue(s.observe("sensor.a", "bad", info(), T0, W))
        self.assertFalse(s.pending_due(T0 + timedelta(minutes=4), D))
        s.observe("sensor.a", "good", info(), T0 + timedelta(minutes=4), W)
        self.assertEqual(s.snapshot(), {"pending": {}, "active": {}, "batch": None})

    def test_one_window_groups_multiple_devices_and_recoveries(self):
        s = AvailabilityState()
        s.observe("sensor.a", "bad", info("A"), T0, W)
        s.observe("sensor.b", "bad", info("B"), T0 + timedelta(minutes=2), W)
        s.confirm("sensor.a", T0 + D, W)
        self.assertTrue(s.initial_needed())
        s.batch["immediate_sent"] = True
        s.confirm("sensor.b", T0 + timedelta(minutes=7), W)
        s.observe("sensor.a", "good", info("A"), T0 + timedelta(minutes=11), W)
        s.observe("sensor.b", "good", info("B"), T0 + timedelta(minutes=14), W)
        self.assertEqual([e["kind"] for e in s.batch["events"]], ["OFFLINE", "OFFLINE", "RECOVERED", "RECOVERED"])
        self.assertFalse(s.initial_needed())
        self.assertFalse(s.due(T0 + timedelta(minutes=24)))
        self.assertTrue(s.due(T0 + timedelta(minutes=25)))

    def test_restart_persists_open_batch_and_late_recovery(self):
        s = AvailabilityState()
        s.observe("sensor.a", "bad", info(), T0, W)
        s.confirm("sensor.a", T0 + D, W)
        s.batch["immediate_sent"] = True
        restored = AvailabilityState(s.snapshot())
        self.assertTrue(restored.due(T0 + timedelta(minutes=26)))
        restored.batch = None
        self.assertIn("sensor.a", restored.active)
        restored.observe("sensor.a", "good", info(), T0 + timedelta(minutes=50), W)
        self.assertEqual(restored.batch["events"][0]["kind"], "RECOVERED")
        self.assertFalse(restored.initial_needed())


    def test_two_apis_on_same_device_are_independent(self):
        s = AvailabilityState()
        a = "binary_sensor.api_main"
        b = "binary_sensor.api_settings"
        s.observe(a, "bad", info("tado", True), T0, W)
        s.observe(b, "bad", info("tado", True), T0, W)
        s.confirm(a, T0 + D, W)
        s.confirm(b, T0 + D, W)
        self.assertEqual(set(s.active), {a, b})
        s.observe(a, "good", info("tado", True), T0 + timedelta(minutes=8), W)
        self.assertIn(b, s.active)
        self.assertNotIn(a, s.active)
        self.assertEqual(
            [item["kind"] for item in s.batch["events"]],
            ["OFFLINE", "OFFLINE", "RECOVERED"],
        )

    def test_unknown_does_not_generate_recovery(self):
        s = AvailabilityState()
        s.observe("sensor.a", "bad", info(), T0, W)
        s.confirm("sensor.a", T0 + D, W)
        s.observe("sensor.a", "uncertain", info(), T0 + timedelta(minutes=10), W)
        self.assertIn("sensor.a", s.active)
        self.assertEqual(len(s.batch["events"]), 1)

    def test_repeated_bad_state_does_not_duplicate_outage(self):
        s = AvailabilityState()
        eid = "binary_sensor.api"
        s.observe(eid, "bad", info("API", True), T0, W)
        s.confirm(eid, T0 + D, W)
        self.assertFalse(s.observe(eid, "bad", info("API", True), T0 + D, W))
        self.assertEqual(len(s.batch["events"]), 1)
        s.observe(eid, "good", info("API", True), T0 + timedelta(minutes=7), W)
        s.observe(eid, "bad", info("API", True), T0 + timedelta(minutes=8), W)
        s.confirm(eid, T0 + timedelta(minutes=13), W)
        self.assertEqual([e["kind"] for e in s.batch["events"]], ["OFFLINE", "RECOVERED", "OFFLINE"])


if __name__ == "__main__":
    unittest.main()
