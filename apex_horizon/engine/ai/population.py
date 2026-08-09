"""The population of AI companies.

V26.11 asks for a *population* rather than an opponent: independent
organisations, some cautious, some reckless, some thriving, some failing, all
playing by the rules the player plays by. This module builds that population and
runs it.

They exist so the world is not a backdrop (V26.2, V4.10): the market moves
because other people are trading in it, opportunities the player hesitates over
get taken (V26.6), and their combined buying and selling is a real part of
supply and demand (V26.8, V4.8). None of that is scripted — it falls out of
ordinary companies run by ordinary employees.

An AI company is never told to target the player. V26.6 is explicit that the
competition is not adversarial: they simply act, and sometimes they act first.
"""

from __future__ import annotations

from random import Random
from typing import Any

from ..company import InvestmentCompany
from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import SimulationContext, SimulationEngine, SimulationPhase
from ..values import EntityKind, IdAllocator, Money
from ..world import Industry
from .director import AIDirector

logger = get_logger(__name__)


class AICompanies:
    """Every AI company in the world, and the simulation of them."""

    def __init__(self, *, config: Config | None = None,
                 allocator: IdAllocator | None = None):
        self.config = config or get_config()
        self.allocator = allocator or IdAllocator()
        self.companies: list[InvestmentCompany] = []
        self.directors: dict[str, AIDirector] = {}
        self.market = None
        self.names = None
        self._last_run_day: int | None = None

    # -- building the population ------------------------------------------
    def populate(self, rng: Random, market, names) -> None:
        """Found the world's AI investment companies."""
        self.market = market
        self.names = names
        count = self.config.get_int("ai.company_count")
        low = self.config.get_int("ai.starting_capital_minimum")
        high = self.config.get_int("ai.starting_capital_maximum")
        bias_low = self.config.get_float("ai.risk_bias_minimum")
        bias_high = self.config.get_float("ai.risk_bias_maximum")

        for _ in range(count):
            capital = Money(rng.randint(low, high))
            company = InvestmentCompany(
                company_id=self.allocator.next_id(EntityKind.COMPANY),
                name=names.company_name(Industry.FINANCIAL),
                founded_on_day=0,
                opening_cash=capital,
                config=self.config,
            )
            # Every AI company hires from the same pool the player does, with a
            # bias of its own toward risk — which is what makes the population
            # varied rather than uniformly aggressive (V26.3, V26.4).
            company.employees.risk_bias = rng.uniform(bias_low, bias_high)
            company.employees.recruitment_tier = self.config.get_int("ai.recruitment_tier")
            company.employees.training_allowed = True
            company.attach_market(market, self.allocator)
            self.companies.append(company)
            self.directors[company.id] = AIDirector(
                company, rng=Random(rng.random()), config=self.config
            )

        logger.info("Founded %d AI companies.", len(self.companies))

    # -- simulation --------------------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Run in the Companies phase, before the market settles (V29.5)."""
        engine.register(SimulationPhase.COMPANIES, self.run_day)
        for company in self.companies:
            company.register(engine)

    def run_day(self, context: SimulationContext) -> None:
        if self._last_run_day == context.day_number:
            return
        self._last_run_day = context.day_number
        for company in self.companies:
            if company.bankrupt:
                continue
            director = self.directors.get(company.id)
            if director is not None:
                director.review(context, self.names, self.allocator)

    # -- reading -----------------------------------------------------------
    @property
    def operating(self) -> list[InvestmentCompany]:
        return [company for company in self.companies if not company.bankrupt]

    def ranked(self) -> list[InvestmentCompany]:
        """AI companies by what they are worth, strongest first."""
        return sorted(self.operating, key=lambda company: company.value().amount,
                      reverse=True)

    def statistics(self) -> dict[str, Any]:
        operating = self.operating
        total = Money.zero()
        for company in operating:
            total = total + company.value()
        employed = sum(len(company.employees) for company in operating)
        return {
            "Operating": len(operating),
            "Failed": len(self.companies) - len(operating),
            "Combined value": total,
            "People employed": employed,
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "companies": [
                {
                    "company": company.state(),
                    "director": self.directors[company.id].state(),
                    "risk_bias": company.employees.risk_bias,
                }
                for company in self.companies
            ],
            "last_run_day": self._last_run_day,
        }

    def restore(self, data: dict, *, market, names, rng: Random) -> None:
        self.market = market
        self.names = names
        self.companies = []
        self.directors = {}
        for record in data.get("companies", []):
            saved = record.get("company", {})
            company = InvestmentCompany(
                company_id=saved["id"],
                name=saved["name"],
                founded_on_day=int(saved.get("founded_on_day", 0)),
                config=self.config,
            )
            # The market is attached first so the investment system exists to
            # receive its own saved state, which company.restore then applies.
            if not bool(saved.get("bankrupt", False)):
                company.attach_market(market, self.allocator)
            company.restore(saved)
            company.employees.risk_bias = float(record.get("risk_bias", 0.0))
            company.employees.training_allowed = True
            director = AIDirector(company, rng=Random(rng.random()), config=self.config)
            director.restore(record.get("director", {}))
            self.companies.append(company)
            self.directors[company.id] = director
        self._last_run_day = data.get("last_run_day")
