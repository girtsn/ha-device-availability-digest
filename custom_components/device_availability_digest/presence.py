"""Pure, vendor-neutral household presence decision.

A confirmed Home from ANY Home Assistant Person or trusted labeled source
always wins. If all people are outside Home OR their location is unknown,
and no labeled source confirms Home continuously for the configured delay,
return Away. A sleeping smartphone must not veto Away indefinitely.

This is an occupancy heuristic, not a safety/security alarm: simultaneous
failure of location reporting and trusted Wi-Fi can produce false Away.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

HOME = "home"
AWAY = "away"
UNKNOWN = "unknown"
DEFAULT_AWAY_DELAY = timedelta(minutes=20)


def decide_presence(
    people: Iterable[tuple[str, datetime | None]],
    home_confirmations: Iterable[str],
    now: datetime,
    away_delay: timedelta = DEFAULT_AWAY_DELAY,
    *,
    absence_since: datetime | None = None,
) -> str:
    """Return home / away / unknown using asymmetric evidence.

    people: (HA Person state, last state change time); any Home wins, while
        unknown/unavailable/other zones are acceptable for Away after delay.
    home_confirmations: trusted labeled sources *currently* reporting Home.
    absence_since: when neither people nor labeled sources began confirming
        Home, tracked by the caller. After restarts, begin a fresh delay.

    Wi-Fi disconnection alone never instantly triggers Away, but prolonged
    absence of positive Wi-Fi and GPS Home evidence does.
    """
    people = list(people)
    if list(home_confirmations) or any(state == HOME for state, _ in people):
        return HOME
    # Do not turn an unconfigured household into Away.
    if not people or absence_since is None or absence_since > now:
        return UNKNOWN
    if now - absence_since < away_delay:
        return UNKNOWN
    return AWAY
