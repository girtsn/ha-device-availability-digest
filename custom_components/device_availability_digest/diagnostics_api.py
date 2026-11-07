"""Admin-only read-only WebSocket API for integration-managed diagnostics."""
from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/history",
    vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=90)),
    vol.Optional("limit", default=2500): vol.All(vol.Coerce(int), vol.Range(min=1, max=5000)),
})
@websocket_api.require_admin
@callback
def ws_get_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the bounded history and current monitored outages.

    This contains household movement and network identifiers: restrict to
    administrator accounts. No GPS coordinates or authentication secrets are
    collected. The API is strictly read-only.
    """
    monitors = hass.data.get(DOMAIN, {})
    monitor = next(
        (value for value in monitors.values()
         if hasattr(value, "history") and value.history is not None),
        None,
    )
    if monitor is None:
        connection.send_error(msg["id"], "not_ready", "Integration not configured")
        return
    active = []
    for eid, data in sorted(monitor.state.active.items()):
        active.append({
            "entity_id": eid,
            "name": data.get("name", eid),
            "area": data.get("area", "Unassigned"),
            "scope": data.get("scope", "device"),
            "since": data.get("since"),
            "failure_reason": data.get("failure_reason"),
            "last_successful_update": data.get("last_successful_update"),
        })
    pending = [
        {"entity_id": eid, "name": data.get("name", eid),
         "since": data.get("since"), "area": data.get("area", "Unassigned")}
        for eid, data in sorted(monitor.state.pending.items())
    ]
    connection.send_result(msg["id"], {
        "events": monitor.history.recent(msg["days"], msg["limit"]),
        "active": active,
        "pending": pending,
        "presence": hass.states.get("sensor.home_presence").state
                    if hass.states.get("sensor.home_presence") else "unknown",
        "retention_days": 90,
    })
