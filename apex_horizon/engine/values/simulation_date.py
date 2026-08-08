"""In-game time.

Design Bible V30.4 is explicit: all simulation time is tracked internally as a
single, continuously incrementing day counter, from which the Year / Month /
Week / Day calendar display (V13.6) is *derived* — never the reverse. This makes
the Continuous Simulation principle (V13.7) a structural guarantee rather than a
display convention, and keeps "a day passing" the only primitive the simulation
ever advances.

Real-world timestamps (save creation and modification dates, V16.16) are kept
deliberately separate from this counter, per V30.5; see :mod:`.timestamps`.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Config, get_config

# Weekday names. The Design Bible references named weekdays in the training
# example of V5.9 ("beginning on a Friday ... completes the following Monday"),
# which also establishes seven-day weeks. Day 1 of a playthrough is defined here
# as a Monday; the Design Bible does not specify a starting weekday.
WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class Calendar:
    """The shape of the in-game calendar, loaded from configuration (V15.10)."""

    days_per_week: int = 7
    weeks_per_month: int = 4
    months_per_year: int = 12

    @classmethod
    def from_config(cls, config: Config | None = None) -> Calendar:
        source = config or get_config()
        return cls(
            days_per_week=source.get_int("calendar.days_per_week"),
            weeks_per_month=source.get_int("calendar.weeks_per_month"),
            months_per_year=source.get_int("calendar.months_per_year"),
        )

    @property
    def days_per_month(self) -> int:
        return self.days_per_week * self.weeks_per_month

    @property
    def days_per_year(self) -> int:
        return self.days_per_month * self.months_per_year


_calendar: Calendar | None = None


def get_calendar() -> Calendar:
    """Return the shared calendar, loading it from configuration on first use."""
    global _calendar
    if _calendar is None:
        _calendar = Calendar.from_config()
    return _calendar


def set_calendar(calendar: Calendar | None) -> None:
    """Replace the shared calendar (used by tests and debug tooling)."""
    global _calendar
    _calendar = calendar


@dataclass(frozen=True, order=True)
class SimulationDate:
    """A point in in-game time, stored purely as a day counter (V30.4).

    ``day`` is 1-based: day 1 is the first day of a playthrough. Every calendar
    component is computed from it on demand.
    """

    day: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.day, int) or isinstance(self.day, bool):
            raise TypeError("SimulationDate day must be an int")
        if self.day < 1:
            raise ValueError("SimulationDate day must be 1 or greater")

    # -- movement --------------------------------------------------------
    def advanced(self, days: int = 1) -> SimulationDate:
        """A new date ``days`` later. Dates are immutable, so this never mutates."""
        return SimulationDate(self.day + days)

    def __add__(self, days: int) -> SimulationDate:
        if not isinstance(days, int) or isinstance(days, bool):
            return NotImplemented
        return self.advanced(days)

    def __sub__(self, other: SimulationDate | int) -> SimulationDate | int:
        """Subtracting a date gives elapsed days; subtracting an int gives a date."""
        if isinstance(other, SimulationDate):
            return self.day - other.day
        if isinstance(other, int) and not isinstance(other, bool):
            return self.advanced(-other)
        return NotImplemented

    def days_until(self, other: SimulationDate) -> int:
        """Whole days from this date until ``other`` (negative when in the past)."""
        return other.day - self.day

    # -- derived calendar components (V13.6) -----------------------------
    def _elapsed(self, calendar: Calendar | None = None) -> tuple[Calendar, int]:
        cal = calendar or get_calendar()
        return cal, self.day - 1

    def year(self, calendar: Calendar | None = None) -> int:
        cal, elapsed = self._elapsed(calendar)
        return elapsed // cal.days_per_year + 1

    def day_of_year(self, calendar: Calendar | None = None) -> int:
        cal, elapsed = self._elapsed(calendar)
        return elapsed % cal.days_per_year + 1

    def month(self, calendar: Calendar | None = None) -> int:
        cal, elapsed = self._elapsed(calendar)
        return (elapsed % cal.days_per_year) // cal.days_per_month + 1

    def day_of_month(self, calendar: Calendar | None = None) -> int:
        cal, elapsed = self._elapsed(calendar)
        return elapsed % cal.days_per_month + 1

    def week_of_month(self, calendar: Calendar | None = None) -> int:
        cal, _ = self._elapsed(calendar)
        return (self.day_of_month(cal) - 1) // cal.days_per_week + 1

    def day_of_week(self, calendar: Calendar | None = None) -> int:
        """Day within the week, 1-based (1 = Monday)."""
        cal, elapsed = self._elapsed(calendar)
        return elapsed % cal.days_per_week + 1

    def weekday_name(self, calendar: Calendar | None = None) -> str:
        index = (self.day_of_week(calendar) - 1) % len(WEEKDAY_NAMES)
        return WEEKDAY_NAMES[index]

    # -- boundaries, used to schedule periodic events (V13.9 - V13.11) ----
    def is_first_day_of_week(self, calendar: Calendar | None = None) -> bool:
        return self.day_of_week(calendar) == 1

    def is_first_day_of_month(self, calendar: Calendar | None = None) -> bool:
        return self.day_of_month(calendar) == 1

    def is_first_day_of_year(self, calendar: Calendar | None = None) -> bool:
        return self.day_of_year(calendar) == 1

    def starts_new_week(self, calendar: Calendar | None = None) -> bool:
        """True when this day begins a week other than the playthrough's first."""
        return self.day > 1 and self.is_first_day_of_week(calendar)

    def starts_new_month(self, calendar: Calendar | None = None) -> bool:
        return self.day > 1 and self.is_first_day_of_month(calendar)

    def starts_new_year(self, calendar: Calendar | None = None) -> bool:
        return self.day > 1 and self.is_first_day_of_year(calendar)

    # -- presentation ----------------------------------------------------
    def label(self, calendar: Calendar | None = None) -> str:
        """The V13.6 display format, e.g. "Year 3, Month 8, Week 2, Day 4"."""
        cal = calendar or get_calendar()
        return (
            f"Year {self.year(cal)}, Month {self.month(cal)}, "
            f"Week {self.week_of_month(cal)}, Day {self.day_of_week(cal)}"
        )

    def short_label(self, calendar: Calendar | None = None) -> str:
        """Compact form for tight interface space, e.g. "Y3 M8 W2 D4"."""
        cal = calendar or get_calendar()
        return (
            f"Y{self.year(cal)} M{self.month(cal)} "
            f"W{self.week_of_month(cal)} D{self.day_of_week(cal)}"
        )

    def __str__(self) -> str:
        return self.label()

    def __repr__(self) -> str:
        return f"SimulationDate(day={self.day})"
