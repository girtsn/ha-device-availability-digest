"""UI setup and options for Device Availability Digest.

Initial values are discovered from the running HA instance. No personal IDs
or site-specific notification entity names are present in the public source.
"""
from __future__ import annotations

from typing import Any
import json
import logging
from pathlib import Path

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback

_LOGGER = logging.getLogger(__name__)
PRIVATE_PROFILE = "device_availability_digest_profile.json"


def _read_private_profile(filepath: str) -> dict[str, Any]:
    """Read optional local-only defaults. Never fetch or publish them."""
    try:
        source = Path(filepath)
        if not source.is_file():
            return {}
        with source.open(encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("Profile must contain a JSON object")
        keys = {
            "notify_entity", "email_subject_prefix", "offline_minutes", "window_minutes",
            "excluded_entities", "excluded_device_entities",
            "connectivity_entities", "auto_exclude_tvs", "stale_monitor_enabled",
            "stale_notify_entity", "stale_daily_reminder_enabled",
            "pm25_stuck_low_window_hours", "pm25_recovery_threshold_ugm3",
            "pm25_recovery_minutes",
        }
        result = {key: value for key, value in data.items() if key in keys}
        for key in ("excluded_entities", "excluded_device_entities", "connectivity_entities"):
            if key in result:
                result[key] = _split(result[key])
        return result
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        _LOGGER.exception("Could not read optional Device Availability Digest private profile")
        return {}


from .const import (
    CONF_AUTO_EXCLUDE_TVS,
    CONF_CONNECTIVITY_ENTITIES,
    CONF_EXCLUDED_DEVICE_ANCHORS,
    CONF_EXCLUDED_ENTITIES,
    CONF_NOTIFY,
    CONF_EMAIL_SUBJECT_PREFIX,
    DEFAULT_EMAIL_SUBJECT_PREFIX,
    CONF_OFFLINE_MINUTES,
    CONF_WINDOW_MINUTES,
    DEFAULT_OFFLINE_MINUTES,
    DEFAULT_WINDOW_MINUTES,
    DOMAIN,
)


def _split(value: str | list[str] | None) -> list[str]:
    """Normalize comma/newline separated entity IDs."""
    if isinstance(value, list):
        return sorted({s.strip() for s in value if s.strip()})
    return sorted({s.strip() for s in (value or "").replace("\n", ",").split(",") if s.strip()})


def discover_defaults(hass: HomeAssistant) -> dict[str, Any]:
    """Find a notification target and known noisy device proxies automatically."""
    available = sorted(s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("notify."))
    email = next((eid for eid in available if "email" in eid.lower()), None)
    excluded = sorted(
        s.entity_id for s in hass.states.async_all()
        if s.entity_id.startswith("switch.foscam_")
    )
    # A typical HA site will have one email notifier. User can change it in UI.
    return {
        CONF_NOTIFY: email or (available[0] if available else ""),
        CONF_EMAIL_SUBJECT_PREFIX: DEFAULT_EMAIL_SUBJECT_PREFIX,
        CONF_OFFLINE_MINUTES: DEFAULT_OFFLINE_MINUTES,
        CONF_WINDOW_MINUTES: DEFAULT_WINDOW_MINUTES,
        CONF_EXCLUDED_ENTITIES: excluded,
        # Resolve any detected proxy switch to its entire registered device.
        CONF_EXCLUDED_DEVICE_ANCHORS: excluded[:],
        CONF_CONNECTIVITY_ENTITIES: [],
        CONF_AUTO_EXCLUDE_TVS: True,
        "stale_monitor_enabled": True,
        "stale_notify_entity": "notify.email_girts" if "notify.email_girts" in available else (email or (available[0] if available else "")),
        "stale_daily_reminder_enabled": True,
        "pm25_stuck_low_window_hours": 24,
        "pm25_recovery_threshold_ugm3": 5.0,
        "pm25_recovery_minutes": 45,
    }


def _form(values: dict[str, Any], advanced: bool) -> vol.Schema:
    """Create a schema with already populated values."""
    schema: dict = {
        vol.Required(CONF_NOTIFY, default=values.get(CONF_NOTIFY, "")): str,
        vol.Required(CONF_EMAIL_SUBJECT_PREFIX, default=values.get(CONF_EMAIL_SUBJECT_PREFIX, DEFAULT_EMAIL_SUBJECT_PREFIX)):
            vol.All(str, vol.Length(max=80)),
        vol.Required(CONF_OFFLINE_MINUTES, default=values.get(CONF_OFFLINE_MINUTES, DEFAULT_OFFLINE_MINUTES)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
        vol.Required(CONF_WINDOW_MINUTES, default=values.get(CONF_WINDOW_MINUTES, DEFAULT_WINDOW_MINUTES)):
            vol.All(vol.Coerce(int), vol.Range(min=1, max=1440)),
    }
    if advanced:
        schema.update({
            vol.Required(CONF_AUTO_EXCLUDE_TVS, default=values.get(CONF_AUTO_EXCLUDE_TVS, True)): bool,
            vol.Required("stale_monitor_enabled", default=values.get("stale_monitor_enabled", True)): bool,
            vol.Required("stale_daily_reminder_enabled", default=values.get("stale_daily_reminder_enabled", True)): bool,
            vol.Required("pm25_stuck_low_window_hours", default=values.get("pm25_stuck_low_window_hours", 24)): vol.All(vol.Coerce(int), vol.Range(min=12, max=72)),
            vol.Required("pm25_recovery_threshold_ugm3", default=values.get("pm25_recovery_threshold_ugm3", 5.0)): vol.All(vol.Coerce(float), vol.Range(min=2.0, max=20.0)),
            vol.Required("pm25_recovery_minutes", default=values.get("pm25_recovery_minutes", 45)): vol.All(vol.Coerce(int), vol.Range(min=15, max=180)),
            vol.Required("stale_notify_entity", default=values.get("stale_notify_entity") or values.get(CONF_NOTIFY, "")): str,
            vol.Optional(CONF_EXCLUDED_ENTITIES,
                         default=", ".join(values.get(CONF_EXCLUDED_ENTITIES, []))): str,
            vol.Optional(CONF_EXCLUDED_DEVICE_ANCHORS,
                         default=", ".join(values.get(CONF_EXCLUDED_DEVICE_ANCHORS, []))): str,
            vol.Optional(CONF_CONNECTIVITY_ENTITIES,
                         default=", ".join(values.get(CONF_CONNECTIVITY_ENTITIES, []))): str,
        })
    return vol.Schema(schema)


def _normalize(values: dict[str, Any]) -> dict[str, Any]:
    result = dict(values)
    result[CONF_EMAIL_SUBJECT_PREFIX] = result.get(CONF_EMAIL_SUBJECT_PREFIX, DEFAULT_EMAIL_SUBJECT_PREFIX).strip()
    for key in (CONF_EXCLUDED_ENTITIES, CONF_EXCLUDED_DEVICE_ANCHORS, CONF_CONNECTIVITY_ENTITIES):
        result[key] = _split(result.get(key))
    return result


class AvailabilityDigestConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Register one instance of the local monitor."""

    VERSION = 1

    async def async_step_user(self, user_input: dict | None = None):
        """Prefill the three essential fields; advanced options are editable later."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        discovered = discover_defaults(self.hass)
        private = await self.hass.async_add_executor_job(
            _read_private_profile, self.hass.config.path(PRIVATE_PROFILE)
        )
        discovered.update(private)
        if user_input is not None:
            if not user_input.get(CONF_NOTIFY, "").startswith("notify."):
                return self.async_show_form(
                    step_id="user", data_schema=_form({**discovered, **user_input}, False),
                    errors={CONF_NOTIFY: "invalid_notify"},
                )
            return self.async_create_entry(
                title="Device Availability Digest",
                data=_normalize({**discovered, **user_input}),
            )
        return self.async_show_form(step_id="user", data_schema=_form(discovered, False))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return AvailabilityDigestOptionsFlow()


class AvailabilityDigestOptionsFlow(config_entries.OptionsFlow):
    """Fine-tune defaults, exclusions and explicit connectivity sensors."""

    async def async_step_init(self, user_input: dict | None = None):
        values = {**self.config_entry.data, **self.config_entry.options}
        if not values.get("stale_notify_entity"):
            values["stale_notify_entity"] = (
                "notify.email_girts"
                if self.hass.states.get("notify.email_girts")
                else values.get(CONF_NOTIFY, "")
            )
        if user_input is not None:
            if not user_input.get(CONF_NOTIFY, "").startswith("notify.") or not user_input.get("stale_notify_entity", values.get("stale_notify_entity") or user_input.get(CONF_NOTIFY, "")).startswith("notify."):
                return self.async_show_form(
                    step_id="init", data_schema=_form({**values, **user_input}, True),
                    errors={CONF_NOTIFY: "invalid_notify"},
                )
            return self.async_create_entry(data=_normalize({**values, **user_input}))
        return self.async_show_form(step_id="init", data_schema=_form(values, True))
