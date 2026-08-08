"""Banking conditions.

Design Bible V7.10 requires banks to respond to economic conditions: better loan
offers during strong economies, more conservative lending during weaker ones,
and changes in both available loan amounts and trust requirements. V25.3 adds
the reasoning — borrowing should feel like a strategic decision rather than a
static option, so a strong economy makes expansion easier while a weak one makes
financial discipline matter more.

This module governs the *conditions banks offer*. Loans themselves — taking one,
repaying it, the interest it accrues — belong to the Financial Management System
of V17.13 and arrive with that milestone.

Banks update in the Banks phase, which V29.5 places third in the day, so their
terms always reflect the economic state computed immediately before.
"""

from __future__ import annotations

from dataclasses import dataclass
from random import Random

from ..config import Config, get_config
from ..simulation import SimulationContext, SimulationEngine, SimulationPhase
from ..values import Money, Percentage
from ..world import World
from .economy import EconomySystem


@dataclass(frozen=True)
class LendingTerms:
    """What one bank will offer a company under current conditions."""

    bank_id: str
    bank_name: str
    interest_rate: Percentage
    maximum_loan: Money
    trust_requirement: float
    available: bool

    def describe(self) -> str:
        if not self.available:
            return f"{self.bank_name} will not lend at your current reputation."
        return (
            f"{self.bank_name}: up to {self.maximum_loan.format(decimals=0)} "
            f"at {self.interest_rate.format()} a year."
        )


@dataclass
class BankProfile:
    """A bank's own character, independent of the economic cycle.

    V33.4 asks for variation in size and reputation tier so that company
    reputation (V3.8) meaningfully affects which banks are accessible. A
    higher-tier bank lends more cheaply but expects more of a borrower.
    """

    bank_id: str
    tier: float  # 0.0 = accessible and expensive, 1.0 = selective and cheap


class BankingSystem:
    """Sets the lending conditions banks offer, following the economy (V7.10)."""

    def __init__(self, world: World, economy: EconomySystem, *, config: Config | None = None):
        self.world = world
        self.economy = economy
        self.config = config or get_config()
        self.profiles: dict[str, BankProfile] = {}

    def populate(self, rng: Random) -> None:
        """Give each bank in the world its own tier."""
        for bank in self.world.banks:
            self.profiles[bank.id] = BankProfile(bank_id=bank.id, tier=rng.random())

    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation (Banks is step 3 of the day, V29.5)."""
        engine.register(SimulationPhase.BANKS, self.update_daily)

    def update_daily(self, context: SimulationContext) -> None:
        """Banks hold no daily state of their own; terms are derived on demand.

        Keeping terms derived rather than stored means they can never drift out
        of step with the economic state they are supposed to follow.
        """

    # -- terms ------------------------------------------------------------
    def interest_rate(self, tier: float = 0.5) -> Percentage:
        """The annual rate a bank of this tier currently charges.

        Rates fall as the economy strengthens and rise as it weakens, and a more
        selective bank lends more cheaply (V7.10, V25.3).
        """
        base = self.config.get_float("banking.base_interest_rate")
        sensitivity = self.config.get_float("banking.rate_health_sensitivity")
        rate = base - self.economy.health * sensitivity - tier * 0.015
        # Inflation feeds through to borrowing costs (V7.5, V25.3).
        rate += max(0.0, self.economy.annual_inflation - 0.02)
        return Percentage(str(round(max(0.01, rate), 5)))

    def lending_multiple(self) -> float:
        """How many times company value a bank will lend against."""
        base = self.config.get_float("banking.base_lending_multiple")
        sensitivity = self.config.get_float("banking.lending_health_sensitivity")
        return max(0.2, base + self.economy.health * sensitivity)

    def trust_requirement(self, tier: float = 0.5) -> float:
        """Minimum company reputation a bank will lend to.

        Requirements tighten in a downturn, which is exactly when borrowing is
        most needed — the pressure V7.19 describes.
        """
        base = self.config.get_float("banking.base_trust_requirement")
        sensitivity = self.config.get_float("banking.trust_health_sensitivity")
        required = base - self.economy.health * sensitivity + tier * 0.20
        return max(0.0, min(0.95, required))

    def terms_for(self, bank_id: str, *, company_value: Money, reputation: float) -> LendingTerms:
        """The offer one bank makes to a company with this value and reputation."""
        profile = self.profiles.get(bank_id)
        bank = next((b for b in self.world.banks if b.id == bank_id), None)
        if profile is None or bank is None:
            raise KeyError(f"Unknown bank: {bank_id}")

        required = self.trust_requirement(profile.tier)
        return LendingTerms(
            bank_id=bank_id,
            bank_name=bank.name,
            interest_rate=self.interest_rate(profile.tier),
            maximum_loan=company_value * self.lending_multiple(),
            trust_requirement=required,
            available=reputation >= required,
        )

    def offers(self, *, company_value: Money, reputation: float) -> list[LendingTerms]:
        """Every bank's current offer, best rate first among those available."""
        all_terms = [
            self.terms_for(bank.id, company_value=company_value, reputation=reputation)
            for bank in self.world.banks
        ]
        return sorted(
            all_terms,
            key=lambda terms: (not terms.available, terms.interest_rate.fraction),
        )

    def best_offer(self, *, company_value: Money, reputation: float) -> LendingTerms | None:
        """The cheapest available offer, or ``None`` if no bank will lend."""
        available = [
            terms
            for terms in self.offers(company_value=company_value, reputation=reputation)
            if terms.available
        ]
        return available[0] if available else None

    # -- persistence ------------------------------------------------------
    def state_data(self) -> dict:
        return {"profiles": {bid: p.tier for bid, p in self.profiles.items()}}

    def restore(self, data: dict) -> None:
        self.profiles = {
            bank_id: BankProfile(bank_id=bank_id, tier=float(tier))
            for bank_id, tier in data.get("profiles", {}).items()
        }
