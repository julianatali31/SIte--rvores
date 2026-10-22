from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.models.enums import WateringPhase
from app.services import humanize
from app.services.watering import (
    BadgeColor,
    RuleSpec,
    compute_badge,
    due_at,
    last_water,
    select_rule,
)

UTC = timezone.utc
SP = ZoneInfo("America/Sao_Paulo")
NOW = datetime(2026, 10, 21, 13, 0, tzinfo=UTC)  # 10:00 in São Paulo
RULES = [
    RuleSpec(WateringPhase.NEWLY_PLANTED, 2.0, 90),
    RuleSpec(WateringPhase.ESTABLISHED, 7.0, None),
]


def ago(**kw):
    return NOW - timedelta(**kw)


# --- compute_badge -----------------------------------------------------------

def test_no_record_is_grey():
    assert compute_badge(None, NOW, 2) == BadgeColor.GREY


@pytest.mark.parametrize(
    ("elapsed", "expected"),
    [
        (timedelta(0), BadgeColor.GREEN),
        (timedelta(hours=35, minutes=59), BadgeColor.GREEN),  # just under 75% of 2 days (36h)
        (timedelta(hours=36), BadgeColor.YELLOW),  # exactly at warn threshold
        (timedelta(hours=47, minutes=59), BadgeColor.YELLOW),
        (timedelta(hours=48), BadgeColor.YELLOW),  # exactly due: still on time
        (timedelta(hours=48, seconds=1), BadgeColor.RED),
        (timedelta(days=30), BadgeColor.RED),
    ],
)
def test_badge_thresholds(elapsed, expected):
    assert compute_badge(NOW - elapsed, NOW, 2, 0.75) == expected


def test_warn_ratio_is_configurable():
    last = ago(hours=30)  # 62.5% of 48h
    assert compute_badge(last, NOW, 2, 0.75) == BadgeColor.GREEN
    assert compute_badge(last, NOW, 2, 0.5) == BadgeColor.YELLOW


def test_future_timestamp_counts_as_just_watered():
    assert compute_badge(NOW + timedelta(minutes=5), NOW, 2) == BadgeColor.GREEN


def test_timezone_of_inputs_does_not_matter():
    last_sp = ago(hours=40).astimezone(SP)
    assert compute_badge(last_sp, NOW, 2) == compute_badge(ago(hours=40), NOW, 2) == BadgeColor.YELLOW


def test_naive_datetimes_are_rejected():
    with pytest.raises(ValueError):
        compute_badge(datetime(2026, 10, 20, 8, 0), NOW, 2)


@pytest.mark.parametrize(("interval", "ratio"), [(0, 0.75), (-1, 0.75), (2, 0), (2, 1)])
def test_invalid_parameters(interval, ratio):
    with pytest.raises(ValueError):
        compute_badge(ago(hours=1), NOW, interval, ratio)


def test_due_at():
    assert due_at(None, 2) is None
    assert due_at(ago(days=1), 2) == NOW + timedelta(days=1)


# --- select_rule -------------------------------------------------------------

def test_newly_planted_rule_until_phase_end():
    assert select_rule(ago(days=89, hours=23), NOW, RULES).phase == WateringPhase.NEWLY_PLANTED
    assert select_rule(ago(days=90), NOW, RULES).phase == WateringPhase.ESTABLISHED


def test_rule_without_planting_date_falls_back_to_established():
    assert select_rule(None, NOW, RULES).phase == WateringPhase.ESTABLISHED


def test_rule_missing_raises():
    with pytest.raises(LookupError):
        select_rule(ago(days=1), NOW, [])


# --- last_water (rain counts) ------------------------------------------------

def test_rain_more_recent_than_watering_wins():
    assert last_water(ago(days=3), ago(days=1), ago(days=10)) == (ago(days=1), "rain")


def test_watering_more_recent_than_rain_wins():
    assert last_water(ago(hours=2), ago(days=1), ago(days=10)) == (ago(hours=2), "watering")


def test_rain_before_planting_is_ignored():
    assert last_water(None, ago(days=20), ago(days=10)) == (None, None)


def test_tie_prefers_manual_watering():
    assert last_water(ago(days=1), ago(days=1), ago(days=10)) == (ago(days=1), "watering")


def test_nothing_recorded():
    assert last_water(None, None, ago(days=1)) == (None, None)


# --- humanize ----------------------------------------------------------------

@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (timedelta(seconds=20), "agora mesmo"),
        (timedelta(minutes=5), "há 5 min"),
        (timedelta(hours=3, minutes=10), "há 3 h"),
        (timedelta(hours=26), "há 1 dia"),
        (timedelta(days=2, hours=5), "há 2 dias"),
    ],
)
def test_relative(delta, text):
    assert humanize.relative(NOW - delta, NOW) == text


def test_calendar_label_uses_sao_paulo_time():
    # 2026-10-21 02:00 UTC is 20/10 23:00 in São Paulo -> "ontem" relative to 21/10 10:00 local.
    assert humanize.calendar_label(datetime(2026, 10, 21, 2, 0, tzinfo=UTC), NOW, SP) == "ontem, 23:00"
    assert humanize.calendar_label(datetime(2026, 10, 21, 11, 10, tzinfo=UTC), NOW, SP) == "hoje, 08:10"
    assert humanize.calendar_label(datetime(2026, 10, 19, 11, 10, tzinfo=UTC), NOW, SP) == "seg 19/10, 08:10"


def test_example_from_spec():
    last = datetime(2026, 10, 20, 11, 10, tzinfo=UTC)  # ontem 08:10 local
    text = f"Regada {humanize.relative(last, NOW)} ({humanize.calendar_label(last, NOW, SP)})"
    assert text == "Regada há 1 dia (ontem, 08:10)"


@pytest.mark.parametrize(
    ("days", "text"),
    [
        (0, "plantada hoje"),
        (1, "plantada há 1 dia"),
        (12, "plantada há 12 dias"),
        (60, "plantada há 2 meses"),
        (100, "plantada há 3 meses"),
        (365 * 2 + 70, "plantada há 2 anos e 2 meses"),
        (365 * 3 + 5, "plantada há 3 anos"),
    ],
)
def test_age(days, text):
    assert humanize.age(NOW - timedelta(days=days), NOW, SP) == text
