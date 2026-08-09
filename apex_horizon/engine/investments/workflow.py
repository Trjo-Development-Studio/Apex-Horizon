"""The investment workflow.

Design Bible V8.3 defines it precisely: research discovers an opportunity,
management reviews and approves or rejects it, an investor executes it, the
position is held, and the investor eventually sells — with profit or loss going
to company cash. It runs continuously rather than at fixed intervals (V13.13),
and each stage is independently timed (V8.24).

V8.2 explains why the player is not simply given a buy button: distributing
authority across the three departments is what stops investing collapsing into
one dominant loop (V8.18), and leaves the player managing strategy — hiring,
assignment, training and limits — rather than clicking trades (V8.14).

The workflow runs inside the Employees phase, which V29.7 places fifth in the
day, so the demand it creates is already recorded when the Market updates at
step eight (V29.10).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from ..config import Config, get_config
from ..employees import Department, Employee, RiskTolerance
from ..logging_setup import get_logger
from ..simulation import SimulationContext, SimulationEngine, SimulationPhase
from ..values import EntityKind, IdAllocator, Money, Percentage
from .opportunity import Opportunity, Position, Stage

logger = get_logger(__name__)


class InvestmentSystem:
    """Runs the company's investment operation (V8)."""

    #: Closed positions kept for analytics; older ones are summarised away.
    MAX_CLOSED = 200

    def __init__(self, company, market, *, allocator: IdAllocator | None = None,
                 config: Config | None = None):
        self.config = config or get_config()
        self.company = company
        self.market = market
        self.allocator = allocator or IdAllocator()
        self.opportunities: list[Opportunity] = []
        self.positions: list[Position] = []
        self.closed: list[Position] = []
        self._last_run_day: int | None = None
        #: Called with each position opened and closed, for anything keeping a
        #: tally. Nothing here knows what a statistic is (V15.7).
        self.on_invested: list = []
        self.on_closed: list = []

        # Holdings count toward company assets (V17.9) without the finances
        # module needing to know what an investment is.
        company.finances.register_asset_provider("investments", self.holdings_value)

    # -- access ------------------------------------------------------------
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.is_open]

    def positions_for(self, employee_id: str) -> list[Position]:
        return [p for p in self.open_positions() if p.opened_by == employee_id]

    def pending_review(self) -> list[Opportunity]:
        return [o for o in self.opportunities if o.stage is Stage.DISCOVERED]

    def awaiting_execution(self) -> list[Opportunity]:
        return [o for o in self.opportunities if o.stage is Stage.APPROVED]

    def holdings_value(self) -> Money:
        """What the company's open positions are worth right now."""
        total = Money.zero()
        for position in self.open_positions():
            listing = self.market.listing_for(position.company_id)
            if listing is not None:
                total = total + position.value_at(listing.price)
        return total

    def unrealised_gain(self) -> Money:
        total = Money.zero()
        for position in self.open_positions():
            listing = self.market.listing_for(position.company_id)
            if listing is not None:
                total = total + position.value_at(listing.price) - position.cost_basis
        return total

    def realised_gain(self) -> Money:
        total = Money.zero()
        for position in self.closed:
            total = total + position.realised_gain
        return total

    # -- simulation --------------------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Run each day alongside the employees who do the work (V29.7)."""
        engine.register(SimulationPhase.EMPLOYEES, self.run_day)

    def run_day(self, context: SimulationContext) -> None:
        """Advance every stage of the workflow by one day."""
        if self._last_run_day == context.day_number or self.company.bankrupt:
            return
        self._expire_stale(context)
        self._discover(context)
        self._review(context)
        self._execute(context)
        self._manage_positions(context)
        self._last_run_day = context.day_number

    # -- 1. research discovers (V8.4) --------------------------------------
    def _discover(self, context: SimulationContext) -> None:
        chance = self.config.get_float("investments.discovery_chance_per_point")
        listings = self.market.active_listings()
        if not listings:
            return

        for employee in self.company.employees:
            effectiveness = employee.effectiveness_in(Department.RESEARCH, self.config)
            if effectiveness <= 0:
                continue
            if context.rng.random() > effectiveness * chance:
                continue

            listing = self._choose_listing(employee, listings, context)
            if listing is None:
                continue
            # Research reduces uncertainty; it never removes it (V9.3), so a
            # better researcher produces a better estimate, not a guarantee.
            confidence = min(1.0, effectiveness + 0.15)
            noise = context.rng.gauss(0.0, 0.14 * (1.2 - confidence))
            expected = Percentage(str(round(0.05 + confidence * 0.12 + noise, 5)))

            opportunity = Opportunity(
                id=self.allocator.next_id(EntityKind.OPPORTUNITY),
                company_id=listing.company_id,
                discovered_by=employee.id,
                discovered_on_day=context.day_number,
                confidence=confidence,
                expected_return=expected,
            )
            self.opportunities.append(opportunity)
            employee.research_completed += 1
            employee.gain_experience(Department.RESEARCH, 1.5, self.config)
            employee.record(context.day_number, "Found an investment opportunity", "*")

    def _choose_listing(self, employee: Employee, listings, context):
        """Pick what to look at (V8.4, V9.5).

        This is where research skill actually pays. A skilled researcher
        compares several candidates and favours the one whose underlying
        business is genuinely performing, while a weak one is little better than
        picking at random. That is the edge the company earns by investing in
        its people — without it, buying with a target and a stop in a market
        that moves randomly would have no expected value at all, and no amount
        of good management could ever make the company profitable.

        It remains an edge, not a guarantee: the strongest company can still
        fall, so research reduces uncertainty without removing it (V8.12, V9.3).
        """
        focus = employee.hidden.market_focus
        pool = listings
        if focus:
            world = self.market.world
            matching = [
                listing for listing in listings
                if (company := world.company_by_id(listing.company_id))
                and company.industry.value == focus
            ]
            if matching and context.rng.random() < 0.7:
                pool = matching

        effectiveness = employee.effectiveness_in(Department.RESEARCH, self.config)
        # How many candidates the researcher can meaningfully compare. Even a
        # novice weighs up two, so a new company is not left with no edge at
        # all and therefore no route out of its first year.
        considered = 2 + int(min(6.0, effectiveness * 8))
        if considered <= 1:
            return context.rng.choice(pool)
        sample = [context.rng.choice(pool) for _ in range(considered)]
        return max(sample, key=lambda listing: listing.performance)

    # -- 2 and 3. management reviews and decides (V8.5) --------------------
    def _review(self, context: SimulationContext) -> None:
        pending = self.pending_review()
        if not pending:
            return
        chance = self.config.get_float("investments.review_chance_per_point")
        threshold = Percentage(str(self.config.get_float("investments.minimum_expected_return")))
        reserve = self._cash_reserve()

        for employee in self.company.employees:
            effectiveness = employee.effectiveness_in(Department.MANAGEMENT, self.config)
            if effectiveness <= 0:
                continue
            reviews = int(effectiveness * chance) + (
                1 if context.rng.random() < (effectiveness * chance) % 1 else 0
            )
            for _ in range(reviews):
                pending = self.pending_review()
                if not pending:
                    return
                opportunity = pending[0]
                self._decide(employee, opportunity, threshold, reserve, context)

    def _decide(self, manager: Employee, opportunity: Opportunity,
                threshold: Percentage, reserve: Money, context) -> None:
        """Approve or reject, on expected return, risk and available capital."""
        opportunity.reviewed_by = manager.id
        opportunity.decided_on_day = context.day_number
        manager.approvals += 1
        manager.gain_experience(Department.MANAGEMENT, 1.2, self.config)

        available = self.company.finances.cash - reserve
        if not available.is_positive:
            opportunity.stage = Stage.REJECTED
            opportunity.rejection_reason = "The company has no capital to invest"
            return
        if opportunity.expected_return < threshold:
            opportunity.stage = Stage.REJECTED
            opportunity.rejection_reason = "The expected return is too low"
            return
        # A manager's own judgement: better managers are less easily convinced
        # by thin research, so weak opportunities are filtered rather than
        # passed straight through (V8.5).
        judgement = manager.effectiveness_in(Department.MANAGEMENT, self.config)
        if opportunity.confidence < 0.25 and context.rng.random() < judgement:
            opportunity.stage = Stage.REJECTED
            opportunity.rejection_reason = "The research is not convincing enough"
            return

        opportunity.stage = Stage.APPROVED
        manager.record(context.day_number, "Approved an investment", "+")

    # -- 4. an investor executes (V8.6, V8.8) ------------------------------
    def _execute(self, context: SimulationContext) -> None:
        approved = self.awaiting_execution()
        if not approved:
            return
        reserve = self._cash_reserve()
        minimum = Money(self.config.get_int("investments.minimum_investment"))
        max_positions = self.config.get_int("investments.max_positions_per_investor")

        for employee in self.company.employees:
            if employee.effectiveness_in(Department.INVESTMENT, self.config) <= 0:
                continue
            if len(self.positions_for(employee.id)) >= max_positions:
                # An investor at their limit declines further opportunities
                # until one is sold (V8.22).
                continue

            approved = self.awaiting_execution()
            if not approved:
                return
            opportunity = approved[0]
            listing = self.market.listing_for(opportunity.company_id)
            if listing is None or listing.delisted or not listing.price.is_positive:
                opportunity.stage = Stage.EXPIRED
                continue

            amount = self._position_size(employee, reserve)
            if amount < minimum:
                # Approved but unaffordable: execution waits rather than forcing
                # the company into a negative balance (V8.22).
                continue

            shares = int(amount / listing.price)
            if shares <= 0:
                continue
            spend = listing.price * shares
            position = Position(
                id=self.allocator.next_id(EntityKind.INVESTMENT),
                company_id=opportunity.company_id,
                shares=shares,
                average_price=listing.price,
                opened_on_day=context.day_number,
                opened_by=employee.id,
                target_return=self._target_return(employee),
                stop_loss=self._stop_loss(employee),
            )
            self.company.finances.invest(
                context.day_number, spend, f"Bought {shares} shares"
            )
            for callback in list(self.on_invested):
                callback(spend)
            # The market feels the purchase (V4.8), before prices update today.
            self.market.record_demand(opportunity.company_id, shares)
            self.positions.append(position)
            opportunity.stage = Stage.EXECUTED
            employee.investments_made += 1
            employee.gain_experience(Department.INVESTMENT, 1.8, self.config)
            employee.record(context.day_number, "Opened an investment", "+")

    def _cash_reserve(self) -> Money:
        """What the company keeps back rather than investing (V8.7).

        The larger of a floor and a share of everything the company has to
        invest — cash plus what it already holds. Measuring the share against
        cash alone would shrink it every time cash was spent, converging on
        nothing and leaving the company fully invested anyway; measured against
        the whole portfolio it is a stable target, the way a real firm keeps a
        proportion of its book in cash.

        This is what lets a company accumulate enough to buy another outright,
        which V12.22 requires be paid in full from cash with no financing.
        """
        floor = Money(self.config.get_int("investments.cash_reserve"))
        share = Decimal(str(self.config.get_float("investments.cash_reserve_share")))
        investable = self.company.finances.cash + self.holdings_value()
        proportional = Money(investable.amount * share)
        return proportional if proportional > floor else floor

    def _position_size(self, employee: Employee, reserve: Money) -> Money:
        """How much this investor commits, within their limit (V8.8, V8.13)."""
        available = self.company.finances.cash - reserve
        if not available.is_positive:
            return Money.zero()
        limit = employee.investment_limit
        if not limit.is_positive:
            # With no limit set by the player, an investor deploys a meaningful
            # share of what is free but never the lot — capital that sits idle
            # earns nothing, while committing everything would leave the company
            # unable to act (V8.7).
            limit = available * Decimal("0.35")
        appetite = Decimal(str(employee.hidden.investment_size))
        wanted = limit * appetite
        return wanted if wanted < available else available

    def _target_return(self, employee: Employee) -> Percentage:
        low = self.config.get_float("investments.target_return_cautious")
        high = self.config.get_float("investments.target_return_aggressive")
        return Percentage(str(round(low + (high - low) * _risk_scale(employee), 5)))

    def _stop_loss(self, employee: Employee) -> Percentage:
        low = self.config.get_float("investments.stop_loss_cautious")
        high = self.config.get_float("investments.stop_loss_aggressive")
        return Percentage(str(round(low + (high - low) * _risk_scale(employee), 5)))

    # -- 5 and 6. holding, then selling (V8.9, V8.10) ----------------------
    def _manage_positions(self, context: SimulationContext) -> None:
        maximum_hold = self.config.get_int("investments.maximum_hold_days")
        for position in list(self.open_positions()):
            listing = self.market.listing_for(position.company_id)
            if listing is None:
                continue
            if listing.delisted:
                self._close(position, listing.price, context, "the company was delisted")
                continue

            gain = position.unrealised_return(listing.price)
            held = position.holding_days(context.day_number)
            if gain >= position.target_return:
                self._close(position, listing.price, context, "reached its target")
            elif gain.fraction <= -position.stop_loss.fraction:
                self._close(position, listing.price, context, "hit its stop loss")
            elif held >= maximum_hold:
                self._close(position, listing.price, context, "was held long enough")

    def _close(self, position: Position, price: Money, context: SimulationContext,
               reason: str) -> None:
        proceeds = position.value_at(price)
        gain = self.company.finances.realise_investment(
            context.day_number, proceeds, position.cost_basis, f"Sold shares — {reason}"
        )
        position.closed_on_day = context.day_number
        position.proceeds = proceeds
        position.realised_gain = gain
        position.close_reason = reason
        for callback in list(self.on_closed):
            callback(gain)
        # Selling presses on the price exactly as buying did (V4.8).
        self.market.record_demand(position.company_id, -position.shares)

        self.positions.remove(position)
        self.closed.append(position)
        del self.closed[: -self.MAX_CLOSED]

        employee = self.company.employees.by_id(position.opened_by)
        if employee is not None:
            employee.record(
                context.day_number,
                f"Closed an investment for {gain.format(decimals=0, signed=True)}",
                "+" if gain.is_positive else "-",
            )

    # -- housekeeping ------------------------------------------------------
    def _expire_stale(self, context: SimulationContext) -> None:
        """Opportunities nobody acted on go stale (V8.5: they are discarded)."""
        lifetime = self.config.get_int("investments.opportunity_lifetime_days")
        for opportunity in self.opportunities:
            if not opportunity.is_open:
                continue
            if context.day_number - opportunity.discovered_on_day >= lifetime:
                opportunity.stage = Stage.EXPIRED
        # Keep only what is still live plus a short history for the interface.
        live = [o for o in self.opportunities if o.is_open]
        history = [o for o in self.opportunities if not o.is_open][-60:]
        self.opportunities = history + live

    # -- statistics (V9.12) ------------------------------------------------
    def statistics(self) -> dict[str, Any]:
        closed = self.closed
        wins = sum(1 for p in closed if p.realised_gain.is_positive)
        return {
            "Open positions": len(self.open_positions()),
            "Holdings value": self.holdings_value(),
            "Unrealised": self.unrealised_gain(),
            "Realised": self.realised_gain(),
            "Closed": len(closed),
            "Win rate": f"{(wins / len(closed) * 100):.0f}%" if closed else "—",
            "Awaiting review": len(self.pending_review()),
            "Awaiting execution": len(self.awaiting_execution()),
        }

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "opportunities": [o.state() for o in self.opportunities],
            "positions": [p.state() for p in self.positions],
            "closed": [p.state() for p in self.closed],
            "last_run_day": self._last_run_day,
        }

    def restore(self, data: dict) -> None:
        self.opportunities = [Opportunity.from_state(o) for o in data.get("opportunities", [])]
        self.positions = [Position.from_state(p) for p in data.get("positions", [])]
        self.closed = [Position.from_state(p) for p in data.get("closed", [])]
        self._last_run_day = data.get("last_run_day")


def _risk_scale(employee: Employee) -> float:
    """Risk tolerance as a 0-to-1 scale (V8.13)."""
    order = {
        RiskTolerance.CAUTIOUS: 0.0,
        RiskTolerance.BALANCED: 0.35,
        RiskTolerance.BOLD: 0.7,
        RiskTolerance.AGGRESSIVE: 1.0,
    }
    return order.get(employee.hidden.risk_tolerance, 0.35)
