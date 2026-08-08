"""The player and their personal finances.

Design Bible V1.4 states the rule this module exists to enforce: personal money
and company money are two separate financial systems that must never merge. The
player may move personal cash into the company; the reverse is never allowed,
and company assets always remain inside the company (V3.4, V17.4).

V1.13 sets the only game-ending condition — personal finances reaching
-$250,000. Company bankruptcy alone does not end a playthrough: under the
Company Continuity Rule (V1.3) the player may found a replacement company if
they still have enough personal wealth.
"""

from __future__ import annotations

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import EntityKind, IdAllocator, Money
from .company import PlayerCompany
from .ledger import RevenueCategory

logger = get_logger(__name__)


class Player:
    """The founder, owner, and chief executive (V1.3)."""

    def __init__(
        self,
        name: str,
        *,
        cash: Money | None = None,
        config: Config | None = None,
        allocator: IdAllocator | None = None,
    ):
        self.config = config or get_config()
        self.name = name
        starting = Money(self.config.get_int("player.starting_personal_cash"))
        self.cash = cash if cash is not None else starting
        self.allocator = allocator or IdAllocator()
        self.company: PlayerCompany | None = None
        # Companies founded and lost, so a replacement is recognisably a fresh
        # start rather than a continuation (V2.12).
        self.former_companies: list[str] = []

    # -- founding (V2.4, V3.3) ---------------------------------------------
    @property
    def founding_cost(self) -> Money:
        return Money(self.config.get_int("company.founding_cost"))

    @property
    def refounding_requirement(self) -> Money:
        return Money(self.config.get_int("company.refounding_net_worth_requirement"))

    def can_found_company(self) -> tuple[bool, str]:
        """Whether a company may be founded now, and why not if not."""
        if self.company is not None and not self.company.bankrupt:
            # V1.3: only one investment company at a time.
            return False, "You already run an investment company."
        if self.cash < self.founding_cost:
            return False, (
                f"Founding a company costs {self.founding_cost.format(decimals=0)}; "
                f"you have {self.cash.format(decimals=0)}."
            )
        # A replacement is being founded if a company has already been lost —
        # either previously, or the bankrupt one still held here. Checking only
        # the recorded history would miss the very first refounding, since that
        # record is written when the replacement is created.
        refounding = bool(self.former_companies) or (
            self.company is not None and self.company.bankrupt
        )
        if refounding and self.net_worth() < self.refounding_requirement:
            # The project manager's rule for starting again after a failure.
            return False, (
                "After a bankruptcy you need a personal net worth of at least "
                f"{self.refounding_requirement.format(decimals=0)} to found a new company."
            )
        return True, ""

    def found_company(self, name: str, day: int) -> tuple[PlayerCompany | None, str]:
        """Found the player's investment company (V2.4, V3.3).

        The founding cost leaves personal cash. By default it becomes the new
        company's opening capital, which is the reading that makes the company
        usable from its first day; the alternative is configurable.
        """
        allowed, reason = self.can_found_company()
        if not allowed:
            return None, reason

        if self.company is not None and self.company.bankrupt:
            self.former_companies.append(self.company.name)

        self.cash = self.cash - self.founding_cost
        becomes_capital = self.config.get_bool("company.founding_cost_becomes_capital")
        opening = self.founding_cost if becomes_capital else Money.zero()

        company = PlayerCompany(
            company_id=self.allocator.next_id(EntityKind.COMPANY),
            name=name,
            founded_on_day=day,
            opening_cash=opening,
            config=self.config,
        )
        if becomes_capital and opening.is_positive:
            company.finances.ledger.record_financing_in(
                day, RevenueCategory.CAPITAL_INJECTION, opening, "Founding capital"
            )
        self.company = company
        logger.info("%s founded %s on day %d.", self.name, name, day)
        return company, f"{name} founded."

    # -- transfers (V1.4, V3.4) --------------------------------------------
    def transfer_to_company(self, amount: Money, day: int) -> tuple[bool, str]:
        """Move personal cash into the company. The reverse is never permitted."""
        if self.company is None or self.company.bankrupt:
            return False, "You have no operating company to fund."
        if not amount.is_positive:
            return False, "Transfer amount must be positive."
        if amount > self.cash:
            return False, "You do not have that much personal cash."
        self.cash = self.cash - amount
        self.company.receive_capital(day, amount)
        return True, f"Transferred {amount.format(decimals=0)} to {self.company.name}."

    # -- worth and failure -------------------------------------------------
    def company_equity(self) -> Money:
        """The player's stake in their company, if it is still operating."""
        if self.company is None or self.company.bankrupt:
            return Money.zero()
        return self.company.value()

    def net_worth(self) -> Money:
        """Personal net worth: personal cash plus the company the player owns.

        The Design Bible measures success partly by personal net worth (V1.6)
        while keeping the two pools of money separate (V1.4). Ownership of the
        company is what links them: the money stays inside the company, but its
        value belongs to the player's overall worth.
        """
        return self.cash + self.company_equity()

    @property
    def bankruptcy_threshold(self) -> Money:
        return Money(self.config.get_int("player.personal_bankruptcy_threshold"))

    def is_personally_bankrupt(self) -> bool:
        """The only game-ending condition (V1.13)."""
        return self.cash <= self.bankruptcy_threshold

    def summary(self) -> dict[str, object]:
        return {
            "Name": self.name,
            "Personal Cash": self.cash,
            "Net Worth": self.net_worth(),
            "Company": self.company.name if self.company else "None",
            "Companies Lost": len(self.former_companies),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "name": self.name,
            "cash": str(self.cash.amount),
            "former_companies": list(self.former_companies),
            "company": self.company.state() if self.company else None,
        }

    def restore(self, data: dict) -> None:
        self.name = data.get("name", self.name)
        self.cash = Money(data.get("cash", "0"))
        self.former_companies = list(data.get("former_companies", []))
        company_state = data.get("company")
        if company_state:
            company = PlayerCompany(
                company_id=company_state["id"],
                name=company_state["name"],
                founded_on_day=int(company_state["founded_on_day"]),
                config=self.config,
            )
            company.restore(company_state)
            self.company = company
        else:
            self.company = None
