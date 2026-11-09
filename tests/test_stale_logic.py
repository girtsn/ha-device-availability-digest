"""Regression tests for stale reports and the opt-in frozen-value heuristic."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest"))
from stale_logic import classify, eligible_measurement, group_for, timeout_hours

NOW = datetime(2026, 11, 9, 20, 0, tzinfo=timezone.utc)


def ago(hours):
    return NOW - timedelta(hours=hours)


def assessment(value="21.0", reported=1, changed=30, bad_since=None,
               group="ambient", timeout=48, frozen=False):
    return classify(
        now=NOW, state=value, last_reported=ago(reported),
        last_changed=ago(changed),
        bad_since=ago(bad_since) if bad_since is not None else None,
        timeout=timeout, group=group, frozen_watch=frozen,
    )


class StaleLogicTests(unittest.TestCase):
    def test_group_thresholds_and_overrides(self):
        self.assertEqual(group_for("sensor.bedroom_pm2_5", ""), "air")
        self.assertEqual(group_for("sensor.voc_index", ""), "air")
        self.assertEqual(group_for("sensor.living_room", "humidity"), "ambient")
        self.assertEqual(group_for("sensor.solar", "power"), "electrical")
        self.assertEqual(timeout_hours("air", set()), 12)
        self.assertEqual(timeout_hours("ambient", set()), 48)
        self.assertEqual(timeout_hours("electrical", set()), 72)
        self.assertEqual(timeout_hours("other", set()), 168)
        self.assertEqual(timeout_hours("ambient", {"stale_monitor_fast"}), 3)
        self.assertEqual(timeout_hours("air", {"stale_monitor_slow"}), 168)

    def test_real_device_numeric_measurements(self):
        self.assertTrue(eligible_measurement(
            "sensor.bedroom_temperature", "22", {"device_class": "temperature"},
            True, None, set(),
        ))
        self.assertTrue(eligible_measurement(
            "sensor.bedroom_pm2_5", "unavailable", {"device_class": "pm25"},
            True, None, set(),
        ))
        self.assertTrue(eligible_measurement(
            "sensor.custom_ambient", "0", {"unit_of_measurement": "ppm"},
            True, None, set(),
        ))

    def test_no_link_speed_battery_total_or_virtual_devices(self):
        examples = [
            ("sensor.tv_link_speed", "2400", {"unit_of_measurement": "Mbit/s"}, None, False),
            ("sensor.battery_level", "89", {"device_class": "battery"}, None, False),
            ("sensor.energy", "1", {"state_class": "total_increasing"}, None, False),
            ("sensor.device_rssi", "-70", {"unit_of_measurement": "dBm"}, None, False),
            ("sensor.cpu_temp", "50", {"device_class": "temperature"}, "diagnostic", False),
            ("sensor.real_temperature", "20", {"device_class": "temperature"}, None, True),
        ]
        for eid, state, attrs, category, virtual in examples:
            with self.subTest(eid=eid):
                self.assertFalse(eligible_measurement(
                    eid, state, attrs, True, category, set(), virtual,
                ))
        self.assertFalse(eligible_measurement(
            "sensor.template_temperature", "20", {"device_class": "temperature"},
            False, None, set(),
        ))

    def test_labels_are_explicit_and_ignore_wins(self):
        args = ("sensor.frozen", "unknown", {}, False, "diagnostic")
        self.assertTrue(eligible_measurement(*args, {"stale_monitor_include"}))
        self.assertFalse(eligible_measurement(
            *args, {"stale_monitor_include", "stale_monitor_ignore"}
        ))

    def test_recent_report_is_healthy_even_when_value_is_unchanged(self):
        self.assertEqual(assessment(value="0", reported=0.2, changed=200)[0], "healthy")
        self.assertEqual(assessment(value="0", reported=0.2, changed=200, frozen=True)[0], "suspect")
        self.assertEqual(assessment(reported=49)[0:2], ("stale", "no_report"))
        self.assertEqual(assessment(reported=48)[0], "stale")
        self.assertEqual(assessment(reported=47.9)[0], "healthy")

    def test_unknown_and_unavailable_have_independent_grace(self):
        self.assertEqual(assessment(value="unknown", reported=100, changed=10)[0], "pending")
        self.assertEqual(assessment(value="unknown", reported=1, changed=25)[0], "stale")
        self.assertEqual(assessment(value="unavailable", reported=0.1, changed=1, bad_since=30)[0], "stale")
        self.assertEqual(assessment(value="unavailable", changed=1, bad_since=20)[0], "pending")
        self.assertEqual(assessment(value="unavailable", changed=12, group="air", timeout=12)[0], "stale")

    def test_fast_grace_and_time_clamping(self):
        self.assertEqual(assessment(value="unknown", changed=4, timeout=3)[0], "stale")
        self.assertEqual(assessment(reported=-4, changed=-5)[2], 0.0)


if __name__ == "__main__":
    unittest.main()
