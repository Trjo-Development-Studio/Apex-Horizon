"""The simulation engine.

Design Bible V15.4 describes a hybrid architecture: a central engine manages
overall game progression while individual systems remain modular, each keeping
its own responsibilities. This module is that centre. It owns in-game time,
executes the ten daily phases of Volume 29 in their defined order, fires the
weekly, monthly, and yearly progression events of V13.9-V13.11, and drives the
seeded randomness that keeps a reloaded world identical (V15.11).

Systems do not import one another through the engine; they register handlers for
the phases they belong to and receive a :class:`SimulationContext` describing the
day being processed (V15.6, V15.7).

**Handlers must be retry-safe.** V15.26 requires an error during a simulation
tick to be caught by the retry policy of V15.13 without corrupting state, so a
handler that fails partway may be invoked again for the same day. Handlers
should therefore apply their changes atomically, or be safe to repeat.
"""

from __future__ import annotations

import random
from collections import defaultdict

from ..config import Config, get_config
from ..errors import run_with_retry
from ..logging_setup import get_logger
from ..values import SimulationDate
from .clock import SimulationClock
from .phases import (
    PHASE_ORDER,
    BoundaryHandler,
    PeriodBoundary,
    PhaseHandler,
    SimulationContext,
    SimulationPhase,
)

logger = get_logger(__name__)


class SimulationEngine:
    """Advances in-game time and runs every registered system in order."""

    def __init__(
        self,
        *,
        start_date: SimulationDate | None = None,
        seed: int | None = None,
        clock: SimulationClock | None = None,
        config: Config | None = None,
    ):
        source = config or get_config()
        self.date = start_date or SimulationDate(1)
        self.clock = clock or SimulationClock(config=source)
        self.seed = (
            seed if seed is not None else source.get_int("simulation.default_random_seed")
        )
        # A single seeded generator drives every system, so replaying a save
        # reproduces the same world exactly (V15.11).
        self.rng = random.Random(self.seed)
        self.background_every_ticks = source.get_int("simulation.background_update_every_ticks")
        self._random_event_chances = {
            PeriodBoundary.WEEK: source.get_float("random_events.weekly_chance"),
            PeriodBoundary.MONTH: source.get_float("random_events.monthly_chance"),
            PeriodBoundary.YEAR: source.get_float("random_events.yearly_chance"),
        }
        self._daily_event_chance = source.get_float("random_events.daily_chance")

        self.tick = 0  # Completed in-game days since the world began.
        self._phase_handlers: dict[SimulationPhase, list[PhaseHandler]] = defaultdict(list)
        self._boundary_handlers: dict[PeriodBoundary, list[BoundaryHandler]] = defaultdict(list)
        self._background_handlers: list[PhaseHandler] = []
        self._random_event_handlers: list[BoundaryHandler] = []

    # -- registration ----------------------------------------------------
    def register(self, phase: SimulationPhase, handler: PhaseHandler) -> None:
        """Register a system to run during ``phase`` of each day (V29.2)."""
        self._phase_handlers[phase].append(handler)

    def register_boundary(self, boundary: PeriodBoundary, handler: BoundaryHandler) -> None:
        """Register a handler for completed weeks, months, or years (V13.9-V13.11)."""
        self._boundary_handlers[boundary].append(handler)

    def register_background(self, handler: PhaseHandler) -> None:
        """Register a periodic background update (V13.19)."""
        self._background_handlers.append(handler)

    def register_random_event(self, handler: BoundaryHandler) -> None:
        """Register a handler invoked when a random event fires (V13.18)."""
        self._random_event_handlers.append(handler)

    # -- running ---------------------------------------------------------
    def update(self, real_seconds: float) -> int:
        """Advance the simulation by however many days ``real_seconds`` earned.

        Returns the number of in-game days simulated. Because the clock reports
        only whole days, calling this once per frame or once per second produces
        identical results (V13.29).
        """
        days = self.clock.advance(real_seconds)
        for _ in range(days):
            self.step_day()
        return days

    def run_days(self, days: int) -> None:
        """Simulate ``days`` in-game days immediately, ignoring the clock.

        Used by tests and by the terminal debug commands of V15.18, which are
        thin wrappers around ordinary simulation APIs rather than bypasses
        (V15.28).
        """
        if days < 0:
            raise ValueError("Cannot simulate a negative number of days")
        for _ in range(days):
            self.step_day()

    def step_day(self) -> SimulationContext:
        """Process exactly one in-game day, then advance to the next.

        Phases run strictly in the Volume 29 order, each completing before the
        next begins, so no system ever observes partially-computed data from a
        later step (V29.13, V29.15).
        """
        context = SimulationContext(
            date=self.date,
            rng=self.rng,
            day_number=self.date.day,
            tick=self.tick,
        )

        for phase in PHASE_ORDER:
            for handler in self._phase_handlers[phase]:
                self._invoke(handler, context, f"Simulation phase {phase.name}")

        self._run_completed_periods(context)
        self._maybe_run_background(context)
        self._roll_random_event(self._daily_event_chance, context, "daily")

        self.tick += 1
        self.date = self.date.advanced(1)
        return context

    # -- internals -------------------------------------------------------
    def _invoke(self, handler, context: SimulationContext, description: str) -> None:
        """Run a handler under the retry policy so one failure cannot end the game."""
        run_with_retry(lambda: handler(context), description=f"{description} on {context}")

    def _run_completed_periods(self, context: SimulationContext) -> None:
        """Fire weekly, monthly, and yearly events for periods ending today.

        V13.9 ties weekly events to *completed* weeks, so these run on the final
        day of each period, after that day's phases have settled. A single day
        can complete several periods at once — the last day of a year is also the
        last day of its month and week — and they fire from shortest to longest.
        """
        completed = (
            (PeriodBoundary.WEEK, self.date.is_last_day_of_week()),
            (PeriodBoundary.MONTH, self.date.is_last_day_of_month()),
            (PeriodBoundary.YEAR, self.date.is_last_day_of_year()),
        )
        for boundary, has_completed in completed:
            if not has_completed:
                continue
            for handler in self._boundary_handlers[boundary]:
                self._invoke(handler, context, f"{boundary.value.capitalize()} progression")
            self._roll_random_event(
                self._random_event_chances[boundary], context, boundary.value
            )

    def _maybe_run_background(self, context: SimulationContext) -> None:
        """Run background updates roughly every five ticks (V13.19)."""
        if self.background_every_ticks <= 0:
            return
        if self.tick % self.background_every_ticks != 0:
            return
        for handler in self._background_handlers:
            self._invoke(handler, context, "Background update")

    def _roll_random_event(self, chance: float, context: SimulationContext, scale: str) -> None:
        """Roll for a random event at one time scale (V13.18).

        The engine decides only *whether* an event occurs; what actually happens
        is supplied by the systems that register handlers, drawing on the Events
        database described in V33.14.
        """
        if chance <= 0 or not self._random_event_handlers:
            return
        if self.rng.random() >= chance:
            return
        logger.debug("Random event triggered at %s scale on %s", scale, context)
        for handler in self._random_event_handlers:
            self._invoke(handler, context, f"Random event ({scale})")

    # -- persistence -----------------------------------------------------
    def state(self) -> dict:
        """Serialisable engine state for inclusion in a save (V16.11).

        The generator's internal state is stored alongside the seed so that a
        reloaded world continues the same random sequence rather than restarting
        it, preserving determinism across saves (V15.11).
        """
        return {
            "day": self.date.day,
            "tick": self.tick,
            "seed": self.seed,
            "rng_state": self.rng.getstate(),
            "clock": self.clock.state(),
        }

    def restore(self, state: dict) -> None:
        """Restore previously saved engine state."""
        self.date = SimulationDate(int(state["day"]))
        self.tick = int(state.get("tick", 0))
        self.seed = int(state.get("seed", self.seed))
        rng_state = state.get("rng_state")
        if rng_state is not None:
            # Tuples survive a round trip through most encodings as lists.
            version, internal, gauss = rng_state
            self.rng.setstate((version, tuple(internal), gauss))
        clock_state = state.get("clock")
        if clock_state:
            self.clock.restore(clock_state)
