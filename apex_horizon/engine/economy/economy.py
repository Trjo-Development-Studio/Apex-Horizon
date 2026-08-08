"""The economy.

Design Bible Volume 7 defines a persistent simulation that continues whether or
not the player acts (V7.3), that the player cannot control but must adapt to
(V7.2), and that applies equally to every participant including AI companies
(V7.13). Volume 25 adds the reasoning: the cycle should be recognisable in
hindsight without being predictable in advance (V25.4), and nothing should
punish the player for reasons they cannot trace (V25.12).

The economy runs in the Economy phase, which V29.4 places second in the day —
after News reports yesterday's settled outcomes, and before Banks, Companies and
the Market, all of which read the freshly computed economic state.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import SimulationContext, SimulationEngine, SimulationPhase
from ..values import Percentage, get_calendar
from ..world import Industry
from .states import EconomicState, derive_state, industry_sensitivity

logger = get_logger(__name__)


@dataclass(frozen=True)
class EconomicTransition:
    """A recorded change of economic condition, for news and analytics."""

    day: int
    previous: EconomicState
    current: EconomicState

    def describe(self) -> str:
        return f"The economy moved from {self.previous} to {self.current}."


class EconomySystem:
    """Simulates economic health, the named states derived from it, and inflation."""

    # Transitions kept for the News System to draw on (V10.7); older ones are
    # discarded so the save cannot grow without bound (V16.20).
    MAX_TRANSITIONS = 50

    def __init__(self, *, config: Config | None = None):
        self.config = config or get_config()
        # A single continuous value in [-1, 1] driving everything (V7.21).
        self.health: float = 0.0
        # Instantaneous rate of change.
        self.velocity: float = 0.0
        # Smoothed rate of change over several weeks. This, not the day's
        # movement, is what distinguishes a Slowdown from a Recovery: day to day
        # the economy is as likely to tick down as up, so an instantaneous
        # reading would report a downturn roughly half the time even in a
        # healthy economy.
        self.trend: float = 0.0
        self.state: EconomicState = EconomicState.STABLE
        self.annual_inflation: float = self.config.get_float("economy.inflation_base")
        # Cumulative price level, starting at 1.0. Over a long playthrough this
        # is what makes nominal cash lose meaning (V25.2).
        self.price_level: float = 1.0
        self.transitions: list[EconomicTransition] = []
        self._last_updated_day: int | None = None

    # -- simulation -------------------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation (Economy is step 2 of the day, V29.4)."""
        engine.register(SimulationPhase.ECONOMY, self.update_daily)

    def update_daily(self, context: SimulationContext) -> None:
        """Advance economic health, inflation, and the derived state."""
        if self._last_updated_day == context.day_number:
            # Retried phases must not advance the economy twice (V15.26).
            return

        self._drift_health(context.rng)
        self._drift_inflation(context.rng)
        self._update_state(context)
        self._last_updated_day = context.day_number

    def _drift_health(self, rng: Random) -> None:
        """Move economic health as a slow, momentum-carrying random walk.

        Momentum is what produces recognisable cycles rather than noise: a
        downturn that has begun tends to continue for a while, which is what
        lets an experienced player read the early signs of a Slowdown before it
        is formally reported (V7.16). Mean reversion stops the economy becoming
        permanently stuck at either extreme.
        """
        drift = self.config.get_float("economy.daily_drift")
        momentum = self.config.get_float("economy.momentum")
        reversion = self.config.get_float("economy.mean_reversion")
        bias = self.config.get_float("economy.health_bias")

        # Reversion pulls toward a mildly positive resting point rather than
        # zero, so expansions are somewhat more common than contractions, as in
        # a real economy. Because the pull acts on velocity rather than health,
        # the pair behave as a damped oscillator whose period is roughly
        # 2*pi/sqrt(reversion) days - which is what sets the length of a
        # business cycle, and why the reversion constant is so small.
        self.velocity = (
            self.velocity * momentum
            + rng.gauss(0.0, drift)
            - (self.health - bias) * reversion
        )
        self.health = max(-1.0, min(1.0, self.health + self.velocity))
        # Damp velocity at the extremes so health does not press against a bound.
        if abs(self.health) >= 1.0:
            self.velocity *= 0.5
        smoothing = self.config.get_float("economy.trend_smoothing")
        self.trend += (self.velocity - self.trend) * smoothing

    def _drift_inflation(self, rng: Random) -> None:
        """Move inflation toward the level implied by economic conditions (V7.5).

        Inflation runs hot in a boom and cools or turns negative in a downturn,
        and moves gradually so its effect is felt across long playthroughs rather
        than short ones.
        """
        base = self.config.get_float("economy.inflation_base")
        sensitivity = self.config.get_float("economy.inflation_health_sensitivity")
        drift = self.config.get_float("economy.inflation_drift")
        low = self.config.get_float("economy.inflation_min")
        high = self.config.get_float("economy.inflation_max")

        target = base + self.health * sensitivity
        self.annual_inflation += (target - self.annual_inflation) * 0.02
        self.annual_inflation += rng.gauss(0.0, drift)
        self.annual_inflation = max(low, min(high, self.annual_inflation))
        self.price_level *= 1.0 + self.daily_inflation

    def _update_state(self, context: SimulationContext) -> None:
        hysteresis = self.config.get_float("economy.state_hysteresis")
        new_state = derive_state(
            self.health,
            self.trend,
            self.state,
            hysteresis,
            self.config.get_float("economy.trend_threshold"),
        )
        if new_state is self.state:
            return
        transition = EconomicTransition(context.day_number, self.state, new_state)
        self.state = new_state
        self.transitions.append(transition)
        del self.transitions[: -self.MAX_TRANSITIONS]
        logger.info("Day %d: %s", context.day_number, transition.describe())

    # -- access -----------------------------------------------------------
    @property
    def daily_inflation(self) -> float:
        """Today's share of the annual inflation rate."""
        return self.annual_inflation / get_calendar().days_per_year

    @property
    def inflation(self) -> Percentage:
        """Annual inflation as a percentage value (V30.3)."""
        return Percentage(str(self.annual_inflation))

    def industry_condition(self, industry: Industry) -> float:
        """How this industry is faring in absolute terms, in [-1, 1] (V7.6).

        Defensive industries barely notice the cycle; cyclical ones amplify it,
        which is what makes diversification a viable strategy (V4.21). This is
        the figure to report to the player.
        """
        return max(-1.0, min(1.0, self.health * industry_sensitivity(industry)))

    def industry_relative_condition(self, industry: Industry) -> float:
        """How this industry fares *relative to the market as a whole*.

        The market applies economic conditions to every company once, through
        its own economic term. If industry trends also tracked absolute health,
        the same boom would be counted twice — and again a third time through
        sentiment — compounding into implausible long-run growth.

        Industries therefore contribute only their *difference* from the average:
        in a boom, cyclical industries outperform and defensive ones lag; in a
        downturn the reverse. Averaged across the market this is close to zero,
        which is exactly right — the aggregate effect of the economy belongs to
        the economy, not to the industries.
        """
        return max(-1.0, min(1.0, self.health * (industry_sensitivity(industry) - 1.0)))

    def is_recession(self) -> bool:
        return self.state is EconomicState.RECESSION

    def is_growing(self) -> bool:
        return self.state in (EconomicState.GROWTH, EconomicState.RECOVERY)

    def describe(self) -> str:
        """A short player-facing summary of conditions."""
        direction = "improving" if self.trend > 0 else "weakening"
        return (
            f"{self.state} — conditions are {direction}, "
            f"inflation {self.inflation.format()} a year."
        )

    def recent_transitions(self, count: int = 5) -> list[EconomicTransition]:
        return self.transitions[-count:]

    # -- persistence ------------------------------------------------------
    def state_data(self) -> dict:
        """Serialisable economy state for the save file (V16.11)."""
        return {
            "health": self.health,
            "velocity": self.velocity,
            "trend": self.trend,
            "state": self.state.name,
            "annual_inflation": self.annual_inflation,
            "price_level": self.price_level,
            "last_updated_day": self._last_updated_day,
            "transitions": [
                {"day": t.day, "previous": t.previous.name, "current": t.current.name}
                for t in self.transitions
            ],
        }

    def restore(self, data: dict) -> None:
        """Restore economy state saved by :meth:`state_data`."""
        self.health = float(data.get("health", 0.0))
        self.velocity = float(data.get("velocity", 0.0))
        self.trend = float(data.get("trend", 0.0))
        self.state = EconomicState[data.get("state", EconomicState.STABLE.name)]
        self.annual_inflation = float(
            data.get("annual_inflation", self.config.get_float("economy.inflation_base"))
        )
        self.price_level = float(data.get("price_level", 1.0))
        self._last_updated_day = data.get("last_updated_day")
        self.transitions = [
            EconomicTransition(
                day=int(entry["day"]),
                previous=EconomicState[entry["previous"]],
                current=EconomicState[entry["current"]],
            )
            for entry in data.get("transitions", [])
        ]
