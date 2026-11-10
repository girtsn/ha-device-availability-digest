"""Regression tests for automatic retirement of invalid monitored incidents.

Exercise the integration's actual methods without installing Home Assistant.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "custom_components" / "device_availability_digest" / "__init__.py"
sys.path.insert(0, str(SOURCE.parent))
from model import AvailabilityState, is_diagnostic_entity, is_link_speed_entity


def method(name):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "AvailabilityDigest")
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    env = {
        "entity_registry": SimpleNamespace(async_get=lambda hass: hass.registry),
        "is_link_speed_entity": is_link_speed_entity,
        "is_diagnostic_entity": is_diagnostic_entity,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[])), str(SOURCE), "exec"), env)
    return env[name]


class Registry:
    def __init__(self, entities):
        self.entities = entities

    def async_get(self, eid):
        return self.entities.get(eid)


class RetiredIncidentTests(unittest.TestCase):
    def test_deleted_disabled_excluded_and_proxy_retire_without_recovery(self):
        names = [
            "sensor.valid", "sensor.deleted", "sensor.disabled",
            "sensor.excluded", "sensor.pc_link_speed",
        ]
        state = AvailabilityState()
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 8, tzinfo=timezone.utc)
        for name in names:
            state.observe(name, "bad", {"cloud": False, "name": name}, start, timedelta(minutes=20))
            state.confirm(name, start + timedelta(minutes=5), timedelta(minutes=20))
        state.batch["immediate_sent"] = True
        states = {
            name: SimpleNamespace(attributes={})
            for name in names if name != "sensor.deleted"
        }
        monitored = {"sensor.valid"}
        monitor = SimpleNamespace(
            state=state,
            hass=SimpleNamespace(states=SimpleNamespace(get=states.get)),
            _monitored=lambda eid, attrs: eid in monitored,
        )
        prune = method("_prune_unmonitored_incidents")
        self.assertTrue(prune(monitor))
        self.assertEqual(set(state.active), monitored)
        self.assertEqual([e["entity_id"] for e in state.batch["events"]], ["sensor.valid"])
        self.assertFalse(prune(monitor))
        self.assertFalse(any(e["kind"] == "RECOVERED" for e in state.batch["events"]))

    def test_monitored_rejects_disabled_diagnostic_and_link_speed(self):
        entries = {
            "sensor.pc_link_speed": SimpleNamespace(device_id="pc", disabled_by=None, entity_category=None),
            "sensor.disabled": SimpleNamespace(device_id="pc", disabled_by="user", entity_category=None),
            "sensor.diagnostic": SimpleNamespace(device_id="pc", disabled_by=None, entity_category="diagnostic"),
            "binary_sensor.api": SimpleNamespace(device_id="pc", disabled_by=None, entity_category="diagnostic"),
            "sensor.real": SimpleNamespace(device_id="pc", disabled_by=None, entity_category=None),
        }
        hass = SimpleNamespace(registry=Registry(entries))
        monitor = SimpleNamespace(
            hass=hass,
            _ignored=lambda eid, did: False,
            _is_cloud=lambda eid, attrs: eid == "binary_sensor.api",
            _is_tado_api=lambda eid, attrs: False,
            _representative=lambda did: "sensor.real",
            connectivity_entities={"binary_sensor.api"},
        )
        monitored = method("_monitored")
        self.assertFalse(monitored(monitor, "sensor.pc_link_speed", {}))
        self.assertFalse(monitored(monitor, "sensor.disabled", {}))
        self.assertFalse(monitored(monitor, "sensor.diagnostic", {}))
        self.assertFalse(monitored(monitor, "sensor.deleted", {}))
        self.assertTrue(monitored(monitor, "binary_sensor.api", {}))
        self.assertTrue(monitored(monitor, "sensor.real", {}))


if __name__ == "__main__":
    unittest.main()
