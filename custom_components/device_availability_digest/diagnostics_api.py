"""Admin-only read-only WebSocket API for integration-managed diagnostics."""
from __future__ import annotations

from typing import Any
from datetime import datetime, timedelta

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN


@websocket_api.websocket_command({
    vol.Required("type"): f"{DOMAIN}/history",
    vol.Optional("days", default=7): vol.All(vol.Coerce(int), vol.Range(min=1, max=90)),
    vol.Optional("limit", default=2500): vol.All(vol.Coerce(int), vol.Range(min=1, max=5000)),
    vol.Optional("start_time"): str,
    vol.Optional("end_time"): str,
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
            "integration": monitor._source_integration(eid),
            "area": data.get("area", "Unassigned"),
            "scope": data.get("scope", "device"),
            "since": data.get("since"),
            "failure_reason": data.get("failure_reason"),
            "last_successful_update": data.get("last_successful_update"),
        })
    pending = [
        {"entity_id": eid, "name": data.get("name", eid),
         "integration": monitor._source_integration(eid),
         "since": data.get("since"), "area": data.get("area", "Unassigned")}
        for eid, data in sorted(monitor.state.pending.items())
    ]
    if "start_time" in msg or "end_time" in msg:
        if "start_time" not in msg or "end_time" not in msg:
            connection.send_error(msg["id"], "invalid_dates", "Both start_time and end_time are required")
            return
        try:
            start = datetime.fromisoformat(msg["start_time"].replace("Z", "+00:00"))
            end = datetime.fromisoformat(msg["end_time"].replace("Z", "+00:00"))
            if (start.tzinfo is None or end.tzinfo is None
                    or not start < end or end - start > timedelta(days=1099)):
                raise ValueError("invalid calendar range")
        except ValueError:
            connection.send_error(msg["id"], "invalid_dates", "Date range must be a valid timezone-aware interval of up to three years")
            return
        events = monitor.history.between(start, end, msg["limit"])
    else:
        # Backward compatibility with v0.3.0 dashboard clients.
        events = monitor.history.recent(msg["days"], msg["limit"])
    connection.send_result(msg["id"], {
        "events": events,
        "active": active,
        "pending": pending,
        "presence": hass.states.get("sensor.home_presence").state
                    if hass.states.get("sensor.home_presence") else "unknown",
        # Current last-Home timestamps are independent of the selected
        # 90-day event-history filter and survive normal HA restarts.
        "source_last_home": dict(monitor.history.last_home),
        "stale": (monitor.stale.snapshot() if monitor.stale is not None
                  else {"enabled": False, "started": False, "rows": [],
                        "counts": {"monitored": 0, "stale": 0, "suspect": 0,
                                   "pending": 0, "healthy": 0},
                        "queued_events": 0, "last_digest": None,
                        "checked_at": None}),
        "retention_days": 90,
    })
