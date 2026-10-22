"""Watering badge rules. Pure functions: no database, no clock.

The caller passes `now` and the last time the tree got water (manual watering
or campus rain, whichever is more recent).
"""
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from app.models.enums import WateringPhase


class BadgeColor(StrEnum):
    GREEN = "green"  # within the interval
    YELLOW = "yellow"  # close to due (past warn_ratio of the interval)
    RED = "red"  # overdue
    GREY = "grey"  # no record yet


@dataclass(frozen=True)
class RuleSpec:
    phase: WateringPhase
    interval_days: float
    phase_until_days: int | None


def _require_aware(*values: datetime | None) -> None:
    for v in values:
        if v is not None and v.tzinfo is None:
            raise ValueError("naive datetime: pass timezone-aware datetimes")


def compute_badge(
    last_water_at: datetime | None,
    now: datetime,
    interval_days: float,
    warn_ratio: float = 0.75,
) -> BadgeColor:
    """Color for the watering badge.

    green   elapsed <  warn_ratio * interval
    yellow  warn_ratio * interval <= elapsed <= interval
    red     elapsed >  interval
    grey    never watered
    A timestamp in the future (clock skew) counts as just watered.
    """
    _require_aware(last_water_at, now)
    if interval_days <= 0:
        raise ValueError("interval_days must be positive")
    if not 0 < warn_ratio < 1:
        raise ValueError("warn_ratio must be between 0 and 1")
    if last_water_at is None:
        return BadgeColor.GREY

    elapsed = max(now - last_water_at, timedelta(0))
    interval = timedelta(days=interval_days)
    if elapsed > interval:
        return BadgeColor.RED
    if elapsed >= interval * warn_ratio:
        return BadgeColor.YELLOW
    return BadgeColor.GREEN


def select_rule(planted_at: datetime | None, now: datetime, rules: Iterable[RuleSpec]) -> RuleSpec:
    """Newly planted rule while within phase_until_days of planting, else established."""
    _require_aware(planted_at, now)
    by_phase = {r.phase: r for r in rules}
    established = by_phase.get(WateringPhase.ESTABLISHED)
    newly = by_phase.get(WateringPhase.NEWLY_PLANTED)
    if newly is not None and planted_at is not None and newly.phase_until_days is not None:
        if now - planted_at < timedelta(days=newly.phase_until_days):
            return newly
    if established is not None:
        return established
    if newly is not None:
        return newly
    raise LookupError("no watering rules configured")


def due_at(last_water_at: datetime | None, interval_days: float) -> datetime | None:
    if last_water_at is None:
        return None
    return last_water_at + timedelta(days=interval_days)


def last_water(
    last_watering_at: datetime | None,
    last_rain_at: datetime | None,
    planted_at: datetime | None,
) -> tuple[datetime | None, str | None]:
    """Most recent water source. Rain before planting does not count for the tree."""
    _require_aware(last_watering_at, last_rain_at, planted_at)
    if last_rain_at is not None and planted_at is not None and last_rain_at < planted_at:
        last_rain_at = None
    candidates = [(t, s) for t, s in ((last_watering_at, "watering"), (last_rain_at, "rain")) if t]
    if not candidates:
        return None, None
    # On a tie, prefer the manual watering (someone actually cared for it).
    return max(candidates, key=lambda c: (c[0], c[1] == "watering"))
