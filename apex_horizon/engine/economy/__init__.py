"""The economy and banking — Design Bible Volumes 7 and 25.

A persistent simulation that continues regardless of the player's actions, that
the player cannot control but must adapt to, and that applies equally to every
participant in the world.
"""

from .banking import BankingSystem, BankProfile, LendingTerms
from .economy import EconomicTransition, EconomySystem
from .states import (
    GROWTH_THRESHOLD,
    INDUSTRY_SENSITIVITY,
    RECESSION_THRESHOLD,
    EconomicState,
    derive_state,
    industry_sensitivity,
)

__all__ = [
    "GROWTH_THRESHOLD",
    "INDUSTRY_SENSITIVITY",
    "RECESSION_THRESHOLD",
    "BankProfile",
    "BankingSystem",
    "EconomicState",
    "EconomicTransition",
    "EconomySystem",
    "LendingTerms",
    "derive_state",
    "industry_sensitivity",
]
