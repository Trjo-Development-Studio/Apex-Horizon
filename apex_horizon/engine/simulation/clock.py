"""Simulation clock — converts real elapsed time into whole in-game days.

Design Bible V13.4 sets the default pace at one real-life second per in-game
day, and V13.5 lets the player run at x1, x2 or x3. V13.29 requires simulation
tick processing to be decoupled from the render frame rate, so the clock
accumulates real time and reports only *whole* days, independent of how often it
is polled: sixty small updates per second and one large update per second
produce exactly the same number of days.

V13.27 additionally requires that rapid speed switching never causes ticks to be
skipped or duplicated. The accumulator is therefore never reset when the speed
changes — only the rate at which it fills.
"""

from __future__ import annotations

from ..config import Config, get_config


class SimulationClock:
    """Accumulates real time and yields whole in-game days."""

    def __init__(
        self,
        *,
        seconds_per_day: float | None = None,
        speed: int | None = None,
        speed_options: tuple[int, ...] | None = None,
        max_days_per_update: int | None = None,
        config: Config | None = None,
    ):
        source = config or get_config()
        self.seconds_per_day = (
            seconds_per_day
            if seconds_per_day is not None
            else source.get_float("simulation.seconds_per_day")
        )
        if self.seconds_per_day <= 0:
            raise ValueError("seconds_per_day must be greater than zero")

        options = speed_options or tuple(source.get_list("simulation.speed_options"))
        self.speed_options: tuple[int, ...] = tuple(int(value) for value in options)
        self._speed = int(
            speed if speed is not None else source.get_int("simulation.default_speed")
        )
        self._validate_speed(self._speed)

        self.max_days_per_update = (
            max_days_per_update
            if max_days_per_update is not None
            else source.get_int("simulation.max_days_per_update")
        )
        # Real seconds banked toward the next in-game day.
        self._accumulator = 0.0
        # Days that could not be simulated within one update's cap (V13.27).
        self._pending_days = 0
        self._paused = False

    # -- speed and pause -------------------------------------------------
    def _validate_speed(self, speed: int) -> None:
        if speed not in self.speed_options:
            raise ValueError(
                f"Unsupported simulation speed {speed!r}; expected one of {self.speed_options}"
            )

    @property
    def speed(self) -> int:
        return self._speed

    @speed.setter
    def speed(self, value: int) -> None:
        """Change speed without disturbing banked time (V13.27)."""
        self._validate_speed(value)
        self._speed = value

    @property
    def paused(self) -> bool:
        """Whether time is currently held.

        V13.20: only popups pause the simulation. The clock exposes the
        mechanism; deciding when to use it belongs to the interface layer.
        """
        return self._paused

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    # -- advancing -------------------------------------------------------
    @property
    def pending_days(self) -> int:
        """Days already earned but not yet released because of the per-update cap."""
        return self._pending_days

    def advance(self, real_seconds: float) -> int:
        """Bank ``real_seconds`` of real time and return whole in-game days to run.

        While paused, time is neither banked nor released, so unpausing never
        fast-forwards through the time spent in a popup (V13.20). Days beyond
        ``max_days_per_update`` are retained and returned by later calls rather
        than discarded, keeping the simulation deterministic across long
        unattended sessions (V13.27).
        """
        if real_seconds < 0:
            raise ValueError("real_seconds cannot be negative")
        if self._paused:
            return 0

        self._accumulator += real_seconds * self._speed
        earned = int(self._accumulator // self.seconds_per_day)
        if earned:
            self._accumulator -= earned * self.seconds_per_day
            self._pending_days += earned

        release = min(self._pending_days, self.max_days_per_update)
        self._pending_days -= release
        return release

    # -- persistence -----------------------------------------------------
    def state(self) -> dict[str, float | int | bool]:
        """Serialisable clock state for inclusion in a save (V16.11)."""
        return {
            "accumulator": self._accumulator,
            "pending_days": self._pending_days,
            "speed": self._speed,
            "paused": self._paused,
        }

    def restore(self, state: dict[str, float | int | bool]) -> None:
        """Restore previously saved clock state."""
        self._accumulator = float(state.get("accumulator", 0.0))
        self._pending_days = int(state.get("pending_days", 0))
        speed = int(state.get("speed", self._speed))
        self._validate_speed(speed)
        self._speed = speed
        self._paused = bool(state.get("paused", False))
