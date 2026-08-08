"""Economic states and how industries respond to them.

Design Bible V7.4 names five conditions the economy moves between, and V7.21
specifies how to model them: as thresholds derived from a single continuous
internal economic health value, rather than as discrete states the simulation
jumps between. That keeps the economy deterministic (V15.11) while letting
transitions feel gradual instead of binary.

Two of the five states are not distinguishable by health alone. A Slowdown and a
Recovery can sit at the same level; what separates them is *direction* — a
Slowdown is falling from strength, a Recovery is climbing out of a downturn. The
state is therefore derived from health **and** trend, which is also what makes
V25.4's "recognisable in hindsight but not perfectly predictable in advance"
possible.
"""

from __future__ import annotations

from enum import Enum

from ..world import Industry


class EconomicState(Enum):
    """The five economic conditions of V7.4."""

    GROWTH = "Economic Growth"
    STABLE = "Stable Economy"
    SLOWDOWN = "Slowdown"
    RECESSION = "Recession"
    RECOVERY = "Recovery"

    def __str__(self) -> str:
        return self.value

    @property
    def is_downturn(self) -> bool:
        return self in (EconomicState.SLOWDOWN, EconomicState.RECESSION)


# Health thresholds separating the strong and weak ends of the range.
GROWTH_THRESHOLD = 0.35
RECESSION_THRESHOLD = -0.35
# How firmly the economy must be trending before direction alone renames the
# state. This is compared against a *smoothed* trend, not a single day's
# movement: day-to-day the economy is as likely to tick down as up, so naming
# the state from instantaneous movement would report a Slowdown roughly half the
# time even in a perfectly healthy economy.
TREND_THRESHOLD = 0.004


def derive_state(
    health: float,
    trend: float,
    previous: EconomicState | None = None,
    hysteresis: float = 0.04,
    trend_threshold: float = TREND_THRESHOLD,
) -> EconomicState:
    """Name the current economic condition from health and its smoothed trend.

    ``hysteresis`` widens each threshold against the state currently in force,
    so the economy must move meaningfully past a boundary before its name
    changes. Without it a value hovering on a threshold would flicker between
    two states, and a reported change would stop meaning anything (V7.4).
    """
    growth_line = GROWTH_THRESHOLD
    recession_line = RECESSION_THRESHOLD
    if previous is EconomicState.GROWTH:
        growth_line -= hysteresis
    if previous is EconomicState.RECESSION:
        recession_line += hysteresis

    if health >= growth_line:
        return EconomicState.GROWTH
    if health <= recession_line:
        return EconomicState.RECESSION

    # Between the extremes the direction of travel decides the name, and the two
    # directional states are deliberately symmetric: following the cycle of
    # V25.4 (Growth -> Stable -> Slowdown -> Recession -> Recovery), a Slowdown
    # is falling *from strength* while a Recovery is climbing *out of weakness*.
    # Testing direction alone, without the corresponding side of the range,
    # makes one of the two far commoner than the other.
    if trend <= -trend_threshold and health > 0.0:
        return EconomicState.SLOWDOWN
    if trend >= trend_threshold and health < 0.0:
        return EconomicState.RECOVERY
    return EconomicState.STABLE


# How strongly each industry responds to economic conditions (V7.6).
#
# The Design Bible requires industries to respond differently to the same
# conditions, and V4.21 notes this is deliberately what makes diversification a
# viable long-term strategy — but it gives no values, so these are authored.
# Defensive industries below 1.0 supply things people buy regardless of the
# cycle; cyclical industries above 1.0 depend on discretionary and capital
# spending, which dries up first in a downturn.
INDUSTRY_SENSITIVITY: dict[Industry, float] = {
    # Defensive
    Industry.HEALTHCARE: 0.30,
    Industry.PHARMACEUTICALS: 0.35,
    Industry.FOOD: 0.40,
    Industry.TELECOMMUNICATIONS: 0.55,
    Industry.ENERGY: 0.65,
    Industry.MEDIA: 0.75,
    # Middling
    Industry.GAMING: 0.90,
    Industry.MANAGEMENT: 1.00,
    Industry.RETAIL: 1.10,
    Industry.ENTERTAINMENT: 1.10,
    Industry.TRANSPORT: 1.15,
    Industry.MANUFACTURING: 1.20,
    Industry.TECHNOLOGY: 1.20,
    # Cyclical
    Industry.SHIPPING: 1.30,
    Industry.HOSPITALITY: 1.30,
    Industry.AEROSPACE: 1.30,
    Industry.FINANCIAL: 1.35,
    Industry.MINING: 1.40,
    Industry.AUTOMOTIVE: 1.40,
    Industry.CONSTRUCTION: 1.50,
}


def industry_sensitivity(industry: Industry) -> float:
    """How strongly ``industry`` follows the economic cycle."""
    return INDUSTRY_SENSITIVITY.get(industry, 1.0)
