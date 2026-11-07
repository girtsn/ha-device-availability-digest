"""Pure, vendor-neutral household presence decision.

Wi-Fi/Bluetooth/other labeled signals can confirm HOME only.
Only all valid, sufficiently old Home Assistant Person location states
can establish AWAY. Unknown or missing location conservatively yields UNKNOWN.
This module has no Home Assistant imports and can be unit tested in isolation.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

HOME = "home"
AWAY = "away"
UNKNOWN = "unknown"
DEFAULT_AWAY_DELAY = timedelta(minutes=20)
INVALID_LOCATIONS = frozenset({"", "unknown", "unavailable", "none"})


def decide_presence(
    people: Iterable[tuple[str, datetime | None]],
    home_confirmations: Iterable[str],
    now: datetime,
    away_delay: timedelta = DEFAULT_AWAY_DELAY,
) -> str:
    """Return home / away / unknown using asymmetric evidence.

    people: (HA Person state, time of last Person state change).
    A named zone other than home (e.g. work) counts as outside Home.
    home_confirmations: entity IDs of trusted sources positively reporting Home.
    """
    people = list(people)
    if home_confirmations or any(state == HOME for state, _ in people):
        return HOME
    if not people:
        return UNKNOWN
    for state, changed in people:
        if state in INVALID_LOCATIONS or changed is None:
            return UNKNOWN
        # Conservative across restarts and clock changes.
        if changed > now or now - changed < away_delay:
            return UNKNOWN
    return AWAY
