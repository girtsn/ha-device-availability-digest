"""Pure-state regression tests; do not require the Home Assistant package."""
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "device_availability_digest"))
from model import AvailabilityState, format_subject, is_nonphysical_device, is_service_device

T0 = datetime(2026, 11, 7, 12, 0, tzinfo=timezone.utc)
D = timedelta(minutes=5)
W = timedelta(minutes=20)


def info(name="device", cloud=False):
    return {"name": name, "area": "test", "cloud": cloud, "scope": "device"}


class DigestTests(unittest.TestCase):
    def test_service_device_filter(self):
        from enum import Enum

        class EntryType(Enum):
            SERVICE = "service"
            DEVICE = "device"

        self.assertTrue(is_service_device("service"))
        self.assertTrue(is_service_device(EntryType.SERVICE))
        self.assertFalse(is_service_device(EntryType.DEVICE))
        self.assertFalse(is_service_device(None))

    def test_tado_zone_is_not_a_physical_device(self):
        # The tado X integration registers heating Zone entries without the
        # HA service entry type. Physical devices have real hardware models.
        self.assertTrue(is_nonphysical_device(None, "Tado", "Zone"))
        self.assertTrue(is_nonphysical_device(None, "tado", " zone "))
        self.assertTrue(is_nonphysical_device("service", "Philips", "Room"))
        self.assertFalse(is_nonphysical_device(None, "Tado", "Home"))
        self.assertFalse(is_nonphysical_device(None, "Tado", "RU02"))
        self.assertFalse(is_nonphysical_device(None, "Tuya", "Zone"))
        self.assertFalse(is_nonphysical_device(None, "Hue", "Smart plug"))
        self.assertFalse(is_nonphysical_device(None, None, None))

    def test_retire_tado_zone_without_retiring_tado_api(self):
        state = AvailabilityState()
        zone = "binary_sensor.0fl_hallway_connectivity"
        api = "binary_sensor.tado_x_api_cloud_connection_state"
        state.observe(zone, "bad", info("0fl hallway", True), T0, W)
        state.observe(api, "bad", info("tado API", True), T0, W)
        state.confirm(zone, T0 + D, W)
        state.confirm(api, T0 + D, W)
        self.assertTrue(state.discard_entities({zone}))
        self.assertNotIn(zone, state.active)
        self.assertIn(api, state.active)
        self.assertEqual(len(state.batch["events"]), 1)
        self.assertEqual(state.batch["events"][0]["entity_id"], api)

    def test_retire_false_room_outage_without_recovery(self):
        state = AvailabilityState()
        state.observe("binary_sensor.room_connectivity", "bad", info("Room"), T0, W)
        state.observe("climate.towel_dryer", "bad", info("Towel dryer"), T0, W)
        state.confirm("binary_sensor.room_connectivity", T0 + D, W)
        state.confirm("climate.towel_dryer", T0 + D, W)
        state.batch["immediate_sent"] = True
        restored = AvailabilityState(state.snapshot())

        self.assertTrue(restored.discard_entities({"binary_sensor.room_connectivity"}))
        self.assertNotIn("binary_sensor.room_connectivity", restored.active)
        self.assertIn("climate.towel_dryer", restored.active)
        self.assertEqual([e["entity_id"] for e in restored.batch["events"]], ["climate.towel_dryer"])
        self.assertFalse(restored.initial_needed())
        self.assertFalse(restored.discard_entities({"binary_sensor.room_connectivity"}))

    def test_retire_only_virtual_events_clears_empty_batch(self):
        state = AvailabilityState()
        eid = "binary_sensor.hue_room_connectivity"
        state.observe(eid, "bad", info("Virtual room"), T0, W)
        state.confirm(eid, T0 + D, W)
        self.assertTrue(state.discard_entities({eid}))
        self.assertEqual(state.active, {})
        self.assertIsNone(state.batch)
        # A later physical outage still opens a normal fresh window.
        state.observe("climate.towel_dryer", "bad", info("Towel dryer"), T0 + D, W)
        state.confirm("climate.towel_dryer", T0 + timedelta(minutes=10), W)
        self.assertTrue(state.initial_needed())


    def test_configurable_email_subject_prefix(self):
        self.assertEqual(format_subject("[HASS]", "OFFLINE: Sauna"), "[HASS] OFFLINE: Sauna")
        self.assertEqual(format_subject("[Home]", "AVAILABILITY SUMMARY: 3"), "[Home] AVAILABILITY SUMMARY: 3")
        self.assertEqual(format_subject("", "OFFLINE: Sauna"), "OFFLINE: Sauna")
        self.assertEqual(format_subject(" [House]  ", "OFFLINE: Sauna"), "[House] OFFLINE: Sauna")

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
