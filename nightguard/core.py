"""Pure scheduling logic; no GUI, network, or OS side effects."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import Enum
import math
import re

COUNTDOWN_SECONDS = 60
SNOOZE_SECONDS = 60
PHRASES = {
    "zh": "我是傻逼，我就是要熬夜",
    "en": "I'm an idiot, and I insist on staying up late.",
}


def minute_of_day(value: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise ValueError("Time must be HH:MM (00:00–23:59)")
    h, m = map(int, value.split(":"))
    return h * 60 + m


@dataclass(frozen=True)
class Schedule:
    start: str = "00:00"
    end: str = "06:00"

    def __post_init__(self):
        if minute_of_day(self.start) == minute_of_day(self.end):
            raise ValueError("Start and end must differ")

    def session(self, now: datetime) -> str | None:
        """Identify the interval by its starting local date; end is exclusive.

        This keeps 'today off' across midnight for a 23:00–06:00 interval.
        Include the schedule in the key so changing hours invalidates old bypasses.
        """
        start, end = minute_of_day(self.start), minute_of_day(self.end)
        minute = now.hour * 60 + now.minute
        day: date = now.date()
        if start < end:
            if not start <= minute < end:
                return None
        else:
            if minute >= start:
                pass
            elif minute < end:
                day -= timedelta(days=1)
            else:
                return None
        return f"{day.isoformat()}|{self.start}|{self.end}"


class Phase(str, Enum):
    IDLE = "idle"
    WARNING = "warning"
    SNOOZED = "snoozed"
    BYPASSED = "bypassed"
    REQUESTED = "requested"


class Engine:
    """One warning at a time. Deadlines are monotonic; windows use local time.

    A >5-second event-loop gap resets an existing countdown to 60 seconds.
    Paired wall-clock/monotonic gaps handle platforms where monotonic stops in
    suspend. No immediate shutdown following resume, DST/time changes or stalls.
    """
    def __init__(self, schedule: Schedule | None = None, enabled: bool = False,
                 bypass_session: str | None = None):
        self.schedule = schedule or Schedule()
        self.enabled = enabled
        self.bypass_session = bypass_session
        self.phase = Phase.IDLE
        self.active_session: str | None = None
        self.deadline: float | None = None
        self.last_tick: float | None = None
        self.last_wall: float | None = None

    def configure(self, schedule: Schedule, enabled: bool):
        if self.schedule != schedule or self.enabled != enabled:
            self.schedule, self.enabled = schedule, enabled
            self.reset()

    def reset(self):
        self.phase = Phase.IDLE
        self.active_session = None
        self.deadline = None
        self.last_tick = None
        self.last_wall = None

    def tick(self, now: datetime, monotonic: float) -> str | None:
        session = self.schedule.session(now) if self.enabled else None
        wall = now.timestamp()
        gap = self.last_tick is not None and (
            monotonic - self.last_tick > 5 or monotonic < self.last_tick
            or abs((wall - self.last_wall) - (monotonic - self.last_tick)) > 5
        )
        self.last_tick, self.last_wall = monotonic, wall
        if not session:
            changed = self.phase != Phase.IDLE
            self.phase, self.active_session, self.deadline = Phase.IDLE, None, None
            return "hide" if changed else None
        if session == self.bypass_session:
            changed = self.phase != Phase.BYPASSED
            self.phase, self.active_session, self.deadline = Phase.BYPASSED, session, None
            return "hide" if changed else None
        if session != self.active_session or self.phase in (Phase.IDLE, Phase.BYPASSED):
            self.active_session = session
            return self._warn(monotonic)
        if gap and self.phase == Phase.WARNING:
            return self._warn(monotonic)
        if self.phase == Phase.SNOOZED and monotonic >= self.deadline:
            return self._warn(monotonic)
        if self.phase == Phase.WARNING and monotonic >= self.deadline:
            self.phase, self.deadline = Phase.REQUESTED, None
            return "shutdown"
        return None

    def _warn(self, monotonic: float) -> str:
        self.phase, self.deadline = Phase.WARNING, monotonic + COUNTDOWN_SECONDS
        return "show"

    def remaining(self, monotonic: float) -> int:
        return max(0, math.ceil((self.deadline or monotonic) - monotonic))

    def snooze(self, monotonic: float) -> bool:
        if self.phase not in (Phase.WARNING, Phase.REQUESTED):
            return False
        self.phase, self.deadline = Phase.SNOOZED, monotonic + SNOOZE_SECONDS
        return True

    def bypass(self, text: str, language: str) -> bool:
        if not self.active_session or self.phase not in (Phase.WARNING, Phase.REQUESTED):
            return False
        if text != PHRASES[language]:
            return False
        self.bypass_session = self.active_session
        self.phase, self.deadline = Phase.BYPASSED, None
        return True
