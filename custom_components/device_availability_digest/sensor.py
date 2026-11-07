"""Generic household Home Presence sensor; independent of notifications.

Home evidence comes from Home Assistant Persons or entity-level sources
labeled "Home Presence". Absence from labeled devices is never proof of Away.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import entity_registry, label_registry
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

from .presence import DEFAULT_AWAY_DELAY, decide_presence

LABEL_NAME = "Home Presence"
ALLOWED_DOMAINS = {"device_tracker", "binary_sensor", "input_boolean", "sensor"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose a separate, read-only Home Presence status."""
    async_add_entities([HomePresenceSensor()])


class HomePresenceSensor(SensorEntity):
    """A conservative occupancy decision reusable by any automation."""

    _attr_name = "Home Presence"
    _attr_unique_id = "device_availability_digest_home_presence"
    _attr_has_entity_name = False
    _attr_icon = "mdi:home-account"
    _attr_should_poll = False
    _attr_native_value = "unknown"

    def __init__(self) -> None:
        """Initialize with a predictable preferred entity ID."""
        self.entity_id = "sensor.home_presence"
        self._attr_extra_state_attributes: dict[str, Any] = {
            "tracked_people": [],
            "active_home_evidence": [],
            "absence_confirmation_minutes": 20,
        }

    @callback
    def _labeled_entities(self) -> list[str]:
        """Read entity-level label assignments, not device labels."""
        registry = label_registry.async_get(self.hass)
        label_ids = {
            label.label_id
            for label in registry.async_list_labels()
            if label.name.casefold() == LABEL_NAME.casefold()
        }
        if not label_ids:
            return []
        result: list[str] = []
        for entry in entity_registry.async_get(self.hass).entities.values():
            if entry.disabled_by is not None or not label_ids.intersection(entry.labels):
                continue
            if entry.entity_id == self.entity_id:
                continue
            if entry.entity_id.split(".", 1)[0] in ALLOWED_DOMAINS:
                result.append(entry.entity_id)
        return sorted(result)

    @callback
    def _refresh(self) -> None:
        """Calculate state and publish only meaningful changes."""
        now = dt_util.utcnow()
        people = sorted(
            (s for s in self.hass.states.async_all("person")),
            key=lambda s: s.entity_id,
        )
        positive: list[str] = []
        for eid in self._labeled_entities():
            state = self.hass.states.get(eid)
            if state is None:
                continue
            domain = eid.split(".", 1)[0]
            if (
                (domain in ("device_tracker", "sensor") and state.state == "home")
                or (domain in ("binary_sensor", "input_boolean") and state.state == "on")
            ):
                positive.append(eid)

        outcome = decide_presence(
            [(p.state, p.last_changed) for p in people],
            positive,
            now,
            DEFAULT_AWAY_DELAY,
        )
        attributes = {
            "tracked_people": [p.entity_id for p in people],
            "active_home_evidence": positive,
            "absence_confirmation_minutes": 20,
        }
        if (
            outcome != self._attr_native_value
            or attributes != self._attr_extra_state_attributes
        ):
            self._attr_native_value = outcome
            self._attr_extra_state_attributes = attributes
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Subscribe to people, labeled source changes and periodic aging."""
        await super().async_added_to_hass()

        @callback
        def on_state(event: Event) -> None:
            eid = event.data.get("entity_id", "")
            if eid.startswith("person.") or eid in self._labeled_entities():
                self._refresh()

        @callback
        def on_registry(_: Event) -> None:
            self._refresh()

        @callback
        def on_tick(_: Any) -> None:
            self._refresh()

        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_STATE_CHANGED, on_state)
        )
        self.async_on_remove(
            self.hass.bus.async_listen("entity_registry_updated", on_registry)
        )
        self.async_on_remove(
            self.hass.bus.async_listen("label_registry_updated", on_registry)
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, on_tick, timedelta(seconds=30))
        )
        self._refresh()
