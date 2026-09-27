from datetime import datetime, timedelta
import pytest

from nightguard.core import Engine, Phase, Schedule, PHRASES, minute_of_day


def at(value):
    return datetime.fromisoformat(value)


def advance(engine, base, start, end):
    result = None
    for second in range(start, end + 1):
        result = engine.tick(base + timedelta(seconds=second), second)
    return result


@pytest.mark.parametrize("start,end,now,expected", [
    ("00:00", "06:00", "2026-09-27T00:00:00", "2026-09-27"),
    ("00:00", "06:00", "2026-09-27T05:59:59", "2026-09-27"),
    ("00:00", "06:00", "2026-09-27T06:00:00", None),
    ("00:00", "06:00", "2026-09-27T23:59:00", None),
    ("23:00", "06:00", "2026-09-27T23:00:00", "2026-09-27"),
    ("23:00", "06:00", "2026-09-28T00:00:00", "2026-09-27"),
    ("23:00", "06:00", "2026-09-28T06:00:00", None),
    ("23:00", "06:00", "2027-01-01T02:00:00", "2026-12-31"),
    ("09:00", "17:00", "2026-09-27T08:59:59", None),
    ("09:00", "17:00", "2026-09-27T09:00:00", "2026-09-27"),
    ("22:00", "00:00", "2026-09-27T23:59:59", "2026-09-27"),
    ("22:00", "00:00", "2026-09-28T00:00:00", None),
])
def test_schedule(start, end, now, expected):
    session = Schedule(start, end).session(at(now))
    assert session == (f"{expected}|{start}|{end}" if expected else None)


@pytest.mark.parametrize("value", ["24:00", "00:60", "7:00", "-1:00", "12:30:00", "ab:cd", None, "1", "00:00\n"])
def test_invalid_times(value):
    with pytest.raises(ValueError):
        minute_of_day(value)


def test_equal_times_rejected():
    with pytest.raises(ValueError):
        Schedule("06:00", "06:00")


def test_one_shutdown_at_sixty_seconds():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    assert engine.tick(base, 0) == "show"
    assert advance(engine, base, 1, 59) is None
    assert engine.remaining(59) == 1
    assert engine.tick(base + timedelta(seconds=60), 60) == "shutdown"
    assert engine.phase == Phase.REQUESTED
    assert engine.tick(base + timedelta(seconds=61), 61) is None


def test_snooze_then_new_full_minute():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    advance(engine, base, 1, 20)
    assert engine.snooze(20)
    assert advance(engine, base, 21, 79) is None
    assert engine.tick(base + timedelta(seconds=80), 80) == "show"
    assert engine.remaining(80) == 60
    assert advance(engine, base, 81, 140) == "shutdown"


def test_end_time_cancels_warning_before_dispatch():
    engine = Engine(enabled=True)
    base = at("2026-09-27T05:59:00")
    engine.tick(base, 0)
    assert advance(engine, base, 1, 60) == "hide"
    assert engine.phase == Phase.IDLE


@pytest.mark.parametrize("language", ["zh", "en"])
def test_exact_phrase_and_today_only(language):
    base = at("2026-09-27T01:00:00")
    engine = Engine(enabled=True)
    engine.tick(base, 0)
    assert not engine.bypass("wrong", language)
    assert not engine.bypass(PHRASES[language] + " ", language)
    assert engine.bypass(PHRASES[language], language)
    restored = Engine(enabled=True, bypass_session=engine.bypass_session)
    assert restored.tick(base, 10) == "hide"
    assert restored.phase == Phase.BYPASSED
    assert restored.tick(base + timedelta(days=1), 100) == "show"


def test_cross_midnight_bypass_survives_calendar_rollover():
    schedule = Schedule("23:00", "06:00")
    engine = Engine(schedule, True)
    engine.tick(at("2026-09-27T23:30:00"), 0)
    assert engine.bypass(PHRASES["zh"], "zh")
    assert engine.tick(at("2026-09-28T02:00:00"), 10) is None
    assert engine.phase == Phase.BYPASSED
    assert engine.tick(at("2026-09-28T23:00:00"), 20) == "show"


def test_disabling_cancels_countdown():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    engine.configure(engine.schedule, False)
    assert engine.tick(base + timedelta(seconds=60), 60) is None
    assert engine.phase == Phase.IDLE


def test_long_event_gap_gets_full_grace_period():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    assert engine.tick(base + timedelta(hours=1), 3600) == "show"
    assert engine.remaining(3600) == 60


def test_sleep_when_monotonic_pauses_also_gets_grace():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    assert engine.tick(base + timedelta(hours=1), 1) == "show"
    assert engine.remaining(1) == 60


def test_clock_moves_backwards_gets_grace():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    assert engine.tick(base - timedelta(minutes=30), 1) == "show"
    assert engine.remaining(1) == 60


def test_outside_window_after_resume_no_shutdown():
    engine = Engine(enabled=True)
    engine.tick(at("2026-09-27T01:00:00"), 0)
    assert engine.tick(at("2026-09-27T07:00:00"), 3600) == "hide"


def test_schedule_change_invalidates_old_exemption():
    engine = Engine(enabled=True)
    now = at("2026-09-27T01:00:00")
    engine.tick(now, 0)
    engine.bypass(PHRASES["en"], "en")
    engine.configure(Schedule("00:00", "07:00"), True)
    assert engine.tick(now, 10) == "show"


def test_disabled_by_default_and_no_actions_outside_warning():
    engine = Engine()
    assert engine.tick(at("2026-09-27T01:00:00"), 0) is None
    assert not engine.snooze(0)
    assert not engine.bypass(PHRASES["en"], "en")


def test_event_loop_gap_must_not_shorten_explicit_snooze():
    engine = Engine(enabled=True)
    base = at("2026-09-27T01:00:00")
    engine.tick(base, 0)
    engine.snooze(0)
    assert engine.tick(base + timedelta(seconds=6), 6) is None
    assert engine.phase == Phase.SNOOZED
    assert engine.remaining(6) == 54
    assert advance(engine, base, 7, 60) == "show"
    assert engine.remaining(60) == 60
