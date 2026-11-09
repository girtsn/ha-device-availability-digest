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
from .const import DOMAIN

LABEL_NAME = "Home Presence"
ALLOWED_DOMAINS = {"device_tracker", "binary_sensor", "input_boolean", "sensor"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Expose a separate, read-only Home Presence status."""
    async_add_entities([HomePresenceSensor(entry.entry_id)])


class HomePresenceSensor(SensorEntity):
    """A conservative occupancy decision reusable by any automation."""

    _attr_name = "Home Presence"
    _attr_unique_id = "device_availability_digest_home_presence"
    _attr_has_entity_name = False
    _attr_icon = "mdi:home-account"
    _attr_should_poll = False
    _attr_native_value = "unknown"

    def __init__(self, entry_id: str) -> None:
        """Initialize with a predictable preferred entity ID."""
        self.entity_id = "sensor.home_presence"
        self._entry_id = entry_id
        self._history = None
        self._initialised = False
        # Dwell time begins once no person or trusted input confirms Home.
        # It is intentionally reset on integration restart for safety.
        self._absence_since = None
        self._labeled_cache: list[str] | None = None
        self._attr_extra_state_attributes: dict[str, Any] = {
            "tracked_people": [],
            "active_home_evidence": [],
            "absence_confirmation_minutes": 20,
        }

    @callback
    def _labeled_entities(self) -> list[str]:
        """Read cached entity-level labels, invalidated on registry updates."""
        if self._labeled_cache is not None:
            return self._labeled_cache
        registry = label_registry.async_get(self.hass)
        label_ids = {
            label.label_id
            for label in registry.async_list_labels()
            if label.name.casefold() == LABEL_NAME.casefold()
        }
        if not label_ids:
            self._labeled_cache = []
            return self._labeled_cache
        result: list[str] = []
        for entry in entity_registry.async_get(self.hass).entities.values():
            if entry.disabled_by is not None or not label_ids.intersection(entry.labels):
                continue
            if entry.entity_id == self.entity_id:
                continue
            if entry.entity_id.split(".", 1)[0] in ALLOWED_DOMAINS:
                result.append(entry.entity_id)
        self._labeled_cache = sorted(result)
        return self._labeled_cache

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

        # A person in unknown/unavailable must not permanently veto Away.
        # Require 20 minutes without ANY positive Home observation instead.
        has_home_evidence = bool(positive) or any(
            p.state == "home" for p in people
        )
        if has_home_evidence or not people:
            self._absence_since = None
        elif self._absence_since is None:
            self._absence_since = now

        outcome = decide_presence(
            [(p.state, p.last_changed) for p in people],
            positive,
            now,
            DEFAULT_AWAY_DELAY,
            absence_since=self._absence_since,
        )
        attributes = {
            "tracked_people": [p.entity_id for p in people],
            "active_home_evidence": positive,
            "absence_confirmation_minutes": 20,
            "absence_candidate_since": (
                self._absence_since.isoformat() if self._absence_since else None
            ),
            "unknown_or_unavailable_people": [
                p.entity_id for p in people
                if p.state in ("unknown", "unavailable")
            ],
            "configured_home_sources": len(self._labeled_entities()),
        }
        previous = self._attr_native_value
        if (
            outcome != previous
            or attributes != self._attr_extra_state_attributes
        ):
            self._attr_native_value = outcome
            self._attr_extra_state_attributes = attributes
            self.async_write_ha_state()

        # Log transitions and initial startup observations, not every poll.
        # The diagnostic log stores entity IDs and zone states but never GPS
        # latitude/longitude from mobile trackers.
        if self._history and (not self._initialised or outcome != previous):
            if any(p.state == "home" for p in people):
                reason = "Person location confirms Home"
            elif positive:
                reason = "Trusted labeled source confirms Home"
            elif outcome == "away":
                reason = (
                    "No positive GPS Person or trusted Wi-Fi Home evidence "
                    "for 20 minutes; unknown Persons do not veto Away"
                )
            else:
                reason = "Waiting for 20 minutes without positive Home evidence"
            self.hass.async_create_task(self._history.record(
                "presence_state",
                previous=previous if self._initialised else None,
                state=outcome,
                reason=reason,
                people=[{"entity_id": p.entity_id, "state": p.state,
                         "source": p.attributes.get("source")}
                        for p in people],
                evidence=positive,
            ))
        self._initialised = True

    async def async_added_to_hass(self) -> None:
        """Subscribe to people, labeled source changes and periodic aging."""
        await super().async_added_to_hass()
        monitor = self.hass.data.get(DOMAIN, {}).get(self._entry_id)
        self._history = getattr(monitor, "history", None)

        @callback
        def on_state(event: Event) -> None:
            eid = event.data.get("entity_id", "")
            if not (eid.startswith("person.") or eid in self._labeled_entities()):
                return
            old = event.data.get("old_state")
            new = event.data.get("new_state")
            before = old.state if old else None
            after = new.state if new else None
            # Include network changes even if the Home/not_home state stays.
            old_attrs = dict(old.attributes) if old else {}
            attrs = dict(new.attributes) if new else {}
            keys = ("mac", "ip", "essid", "ssid", "source")
            changed_network = any(old_attrs.get(k) != attrs.get(k) for k in keys)
            if self._history and (before != after or changed_network):
                source_eid = str(attrs.get("source") or "") if eid.startswith("person.") else eid
                source = self.hass.states.get(source_eid)
                source_attrs = dict(source.attributes) if source else {}
                # A change to MAC, IP, SSID or GPS source is diagnostic
                # information, not a transition from home -> home.
                is_transition = before != after
                changed_details = {
                    key: {"before": old_attrs.get(key), "after": attrs.get(key)}
                    for key in keys if old_attrs.get(key) != attrs.get(key)
                }
                self.hass.async_create_task(self._history.record(
                    "presence_source" if is_transition else "presence_details",
                    entity_id=eid,
                    source_entity_id=source_eid or None,
                    previous=before if is_transition else None,
                    state=after,
                    reason=("Location or presence state changed" if is_transition
                            else "Connection or location-source details updated; presence unchanged"),
                    changed_details=changed_details if changed_network else {},
                    name=str(attrs.get("friendly_name") or eid),
                    mac=attrs.get("mac") or source_attrs.get("mac"),
                    ip=attrs.get("ip") or source_attrs.get("ip"),
                    ssid=attrs.get("essid") or attrs.get("ssid")
                         or source_attrs.get("essid") or source_attrs.get("ssid"),
                ))
            self._refresh()

        @callback
        def on_registry(_: Event) -> None:
            self._labeled_cache = None
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
