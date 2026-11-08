"""Regression tests for device metadata and Home Assistant AreaRegistry API.

Execute the real _info() method without importing Home Assistant, which is not a
dependency in this repository's pure-Python CI tests.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "device_availability_digest"
    / "__init__.py"
)


def load_info_method():
    """Compile the integration's real _info() method in a minimal test context."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    monitor = next(
        item for item in tree.body
        if isinstance(item, ast.ClassDef) and item.name == "AvailabilityDigest"
    )
    method = next(
        item for item in monitor.body
        if isinstance(item, ast.FunctionDef) and item.name == "_info"
    )
    return compile(ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[])), str(SOURCE), "exec")


class AreaRegistryStub:
    """Match the actual AreaRegistry API: async_get_area, not async_get."""

    def __init__(self):
        self.lookups = []
        self.areas = {"first_floor": SimpleNamespace(name="First floor")}

    def async_get_area(self, area_id):
        self.lookups.append(area_id)
        return self.areas.get(area_id)


class MetadataTests(unittest.TestCase):
    def _metadata(self, area_id):
        area_registry = AreaRegistryStub()
        device = SimpleNamespace(
            name_by_user="1fl towel dryer",
            name="Towel heater",
            area_id=area_id,
        )
        namespace = {
            "area_registry": SimpleNamespace(async_get=lambda hass: area_registry),
            "device_registry": SimpleNamespace(
                async_get=lambda hass: SimpleNamespace(async_get=lambda did: device)
            ),
        }
        exec(load_info_method(), namespace)
        monitor = SimpleNamespace(
            hass=object(),
            _device_id=lambda eid: "test-device-id",
            _is_cloud=lambda eid, attrs: False,
            _source_integration=lambda eid: "tuya_local",
        )
        result = namespace["_info"](
            monitor, "climate.1fl_towel_dryer_heating_element", {}
        )
        return result, area_registry.lookups

    def test_assigned_area_resolves_without_attribute_error(self):
        info, lookups = self._metadata("first_floor")
        self.assertEqual(info["name"], "1fl towel dryer")
        self.assertEqual(info["area"], "First floor")
        self.assertEqual(info["scope"], "device")
        self.assertEqual(info["integration"], "tuya_local")
        self.assertFalse(info["cloud"])
        self.assertEqual(lookups, ["first_floor"])

    def test_unassigned_device_uses_fallback(self):
        info, lookups = self._metadata(None)
        self.assertEqual(info["area"], "Unassigned")
        self.assertEqual(lookups, [])

    def test_missing_area_uses_fallback(self):
        info, lookups = self._metadata("deleted_area")
        self.assertEqual(info["area"], "Unassigned")
        self.assertEqual(lookups, ["deleted_area"])


if __name__ == "__main__":
    unittest.main()
