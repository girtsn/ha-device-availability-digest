"""Restart-safe, privacy-minimal diagnostics for presence and availability.

History lives in a *separate* private Home Assistant Store from the outage
state machine. The history is read-only through an administrator-only WebSocket
command; the dashboard never modifies monitoring or email delivery.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.helpers.storage import Store
from .model import utcnow

HISTORY_KEY = "device_availability_digest_history"
MAX_EVENTS = 5000
DAYS_TO_KEEP = 90


class DiagnosticHistory:
    """Bounded chronological event history, persisted across HA restarts."""

    def __init__(self, hass) -> None:
        self.store = Store(hass, 1, HISTORY_KEY, private=True, atomic_writes=True)
        self.events: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()
        self._counter = 0

    async def load(self) -> None:
        data = await self.store.async_load() or {}
        self.events = list(data.get("events", []))[-MAX_EVENTS:]
        self._counter = int(data.get("counter", 0))
        self._prune()

    def _prune(self) -> None:
        cutoff = (utcnow() - timedelta(days=DAYS_TO_KEEP)).isoformat()
        self.events = [
            e for e in self.events if isinstance(e, dict)
            and isinstance(e.get("at"), str) and e["at"] >= cutoff
        ][-MAX_EVENTS:]

    async def record(self, kind: str, **details: Any) -> None:
        """Keep only intentionally supplied, serializable diagnostic fields."""
        async with self._lock:
            self._counter += 1
            row = {"id": self._counter, "kind": kind, "at": utcnow().isoformat()}
            row.update(details)
            self.events.append(row)
            self._prune()
            await self.store.async_save({
                "counter": self._counter,
                "events": self.events,
            })

    def recent(self, days: int = 7, limit: int = 1000) -> list[dict]:
        cutoff = (utcnow() - timedelta(days=days)).isoformat()
        return [dict(e) for e in self.events
                if e["at"] >= cutoff][-limit:]

    def between(self, start: datetime, end: datetime, limit: int = 5000) -> list[dict]:
        """Return events inside an end-exclusive selected calendar range.

        All events are written in UTC. Accept timezone-aware boundaries from
        the frontend's calendar (which respects local midnight and DST).
        """
        if start.tzinfo is None or end.tzinfo is None or start >= end:
            return []
        start_iso = start.astimezone(timezone.utc).isoformat()
        end_iso = end.astimezone(timezone.utc).isoformat()
        return [dict(e) for e in self.events
                if start_iso <= e.get("at", "") < end_iso][-limit:]
