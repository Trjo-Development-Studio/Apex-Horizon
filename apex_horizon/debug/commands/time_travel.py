"""Developer commands that move the clock (V15.18)."""

from __future__ import annotations

from ...engine.values import get_calendar
from .base import TIME_ADD, no


class TimeCommands:
    """``time`` and its subcommands, mixed into :class:`DeveloperCommands`."""

    # -- time --------------------------------------------------------------
    def _time(self, *args: str) -> str:
        engine = self.context.engine
        if engine is None:
            return no("No game is running.")
        if not args:
            now = f"It is {engine.date.label()}."
            return f"{now} Simulating {self.pending_days:,} more day(s)." \
                if self.busy else now

        action = args[0].lower()
        if action == "set":
            return self._time_set(args[1:])
        if action == "add":
            return self._time_add(args[1:])
        if action == "cancel":
            if not self.busy:
                return no("No time jump is running.")
            abandoned, self.pending_days = self.pending_days, 0
            return f"Abandoned {abandoned:,} remaining day(s) at {engine.date.label()}."
        return no("Invalid syntax. Use 'help time' for the exact syntax.")

    def _time_set(self, args: tuple[str, ...]) -> str:
        if len(args) != 4:
            return no("Invalid syntax. Use 'time set {year} {month} {week} {day}'.")
        calendar = get_calendar()
        limits = (
            ("year", None),
            ("month", calendar.months_per_year),
            ("week", calendar.weeks_per_month),
            ("day", calendar.days_per_week),
        )
        values = []
        for text, (label, highest) in zip(args, limits, strict=True):
            try:
                value = int(text)
            except ValueError:
                return no(f"{text} is not a whole number of {label}s.")
            if value < 1:
                return no(f"The {label} must be 1 or greater.")
            if highest is not None and value > highest:
                return no(f"The {label} must be between 1 and {highest}.")
            values.append(value)

        year, month, week, day = values
        target = (
            (year - 1) * calendar.days_per_year
            + (month - 1) * calendar.days_per_month
            + (week - 1) * calendar.days_per_week
            + day
        )
        engine = self.context.engine
        current = engine.date.day + self.pending_days
        if target == current:
            return f"It is already {engine.date.label()}."
        if target < current:
            # The simulation only knows how to live days, not to unlive them.
            return no(
                f"Time only moves forwards. It is already {engine.date.label()}; "
                "start a new game to go back."
            )
        return self._schedule(target - current)

    def _time_add(self, args: tuple[str, ...]) -> str:
        match = TIME_ADD.match("".join(args).lower())
        if match is None:
            return no(
                "Invalid syntax. Use 'time add {amount}{unit}', where unit is "
                "year, month, week or day — for example 'time add 5year'."
            )
        amount, unit = int(match.group(1)), match.group(2)
        if amount < 1:
            return no("Add at least one day.")
        calendar = get_calendar()
        per_unit = {
            "year": calendar.days_per_year,
            "month": calendar.days_per_month,
            "week": calendar.days_per_week,
            "day": 1,
        }[unit]
        return self._schedule(amount * per_unit)
