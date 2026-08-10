"""Running a company through time: loans, bankruptcy and persistence."""

from __future__ import annotations

from random import Random

from company_support import founded_player, make_engine

from apex_horizon.engine.company import (
    ExpenseCategory,
    PeriodTotals,
    Player,
    RevenueCategory,
)
from apex_horizon.engine.economy import BankingSystem, EconomySystem
from apex_horizon.engine.values import IdAllocator, Money, Percentage
from apex_horizon.engine.world import generate_world

# -- running the company through time (V13.9 - V13.11) --------------------


def test_weekly_running_costs_are_charged():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    engine.run_days(7)
    assert company.finances.cash < Money(25_000)
    assert "Operational costs" in company.finances.ledger.by_category


def test_yearly_tax_is_charged_on_profit():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    company.finances.receive(1, RevenueCategory.INVESTMENT_PROFIT, Money(100_000))
    engine.run_days(336)
    assert "Tax" in company.finances.ledger.by_category
    assert company.finances.ledger.by_category["Tax"].is_positive


def test_no_tax_is_charged_on_a_loss():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    engine.run_days(336)
    assert "Tax" not in company.finances.ledger.by_category


def test_reputation_follows_profitability():
    # V3.8: reputation is earned over time, so it is driven directly here rather
    # than through the engine, which would overwrite the month being tested.
    _, company = founded_player()
    start = company.reputation

    company.finances.last_month = PeriodTotals(revenue=Money(100_000))
    for _ in range(400):
        company._drift_reputation()
    improved = company.reputation
    assert improved > start

    company.finances.last_month = PeriodTotals(expenses=Money(100_000))
    for _ in range(400):
        company._drift_reputation()
    assert company.reputation < improved


def test_reputation_moves_slowly():
    # A single profitable month must not buy standing in the industry.
    _, company = founded_player()
    company.finances.last_month = PeriodTotals(revenue=Money(1_000_000))
    before = company.reputation
    company._drift_reputation()
    assert company.reputation - before < 0.01


def test_borrowing_is_never_counted_as_profit():
    # V17.26: the player must not be able to mistake borrowed cash for earnings.
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    company.take_loan(terms, Money(100_000), day=1, allocator=IdAllocator())

    assert company.finances.cash == Money(125_000)
    assert company.finances.profit_this_week.is_zero
    assert company.finances.lifetime_profit.is_zero
    # It does show as cash coming in (V17.5).
    assert company.finances.cash_flow()["Cash In"] == Money(125_000)


def test_repaying_principal_is_not_an_expense():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    company.take_loan(terms, Money(104_000), day=1, allocator=IdAllocator())
    engine = make_engine()
    company.register(engine)
    engine.run_days(7 * 4)

    # Four weeks of principal repayments total $4,000, none of which is a cost;
    # only the interest reduces profit.
    interest = Money.zero()
    for loan in company.loans.loans:
        interest = interest + loan.interest_paid
    assert company.finances.ledger.year.expenses < Money(5_000)
    assert interest.is_positive


def test_company_updates_are_retry_safe():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    engine.run_days(1)
    reputation = company.reputation
    from apex_horizon.engine.simulation import SimulationContext

    context = SimulationContext(date=engine.date - 1, rng=engine.rng, day_number=1, tick=0)
    company.update_daily(context)
    assert company.reputation == reputation


# -- loans (V17.13) --------------------------------------------------------


def build_banking(seed: int = 5):
    world, _, _ = generate_world(seed)
    economy = EconomySystem()
    banking = BankingSystem(world, economy)
    banking.populate(Random(seed))
    return economy, banking


def test_borrowing_adds_cash_and_debt():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    company.reputation = 0.9
    terms = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    loan = company.take_loan(terms, Money(100_000), day=1, allocator=IdAllocator())

    assert loan is not None
    assert company.finances.cash == Money(125_000)
    assert company.loans.total_outstanding() == Money(100_000)
    # Debt counts against net worth (V17.10).
    assert company.finances.net_worth() == Money(25_000)


def test_a_bank_that_will_not_lend_is_refused():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = -1.0
    terms = banking.offers(company_value=Money(1_000), reputation=0.0)[0]
    assert company.take_loan(terms, Money(50_000), 1, IdAllocator()) is None


def test_loan_amounts_outside_the_offer_are_refused():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(100_000), reputation=0.9)
    assert company.take_loan(terms, Money(1), 1, IdAllocator()) is None
    assert company.take_loan(terms, Money(999_000_000), 1, IdAllocator()) is None


def test_loans_are_repaid_weekly_with_interest():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    loan = company.take_loan(terms, Money(52_000), day=1, allocator=IdAllocator())
    engine = make_engine()
    company.register(engine)

    engine.run_days(7 * 4)
    assert loan is not None
    assert loan.outstanding < Money(52_000)
    assert loan.interest_paid.is_positive
    assert "Loan repayments" in company.finances.ledger.by_category


def test_a_loan_is_eventually_repaid_in_full():
    _, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(10_000_000), reputation=0.9)
    loan = company.take_loan(terms, Money(104_000), day=1, allocator=IdAllocator())
    engine = make_engine()
    company.register(engine)

    assert loan is not None
    engine.run_days(7 * 110)
    assert loan.outstanding.is_zero
    assert loan.repaid_on_day is not None
    assert not loan.is_active
    assert company.loans.total_outstanding().is_zero


# -- bankruptcy (V3.14, V17.19, V1.13) ------------------------------------


def test_company_goes_bankrupt_at_the_configured_threshold():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    company.finances.spend(1, ExpenseCategory.INVESTMENTS, Money(1_100_000), "bad bet")
    engine.run_days(1)
    assert company.bankrupt
    assert company.bankrupt_on_day is not None


def test_bankruptcy_notifies_other_systems():
    # Employees, subsidiaries and funds react through callbacks (V15.7).
    _, company = founded_player()
    notified: list[str] = []
    company.on_bankruptcy.append(lambda c: notified.append(c.name))
    company.declare_bankruptcy(day=5)
    assert notified == ["Test Capital"]
    # Declaring twice does not fire the callbacks again.
    company.declare_bankruptcy(day=6)
    assert len(notified) == 1


def test_a_bankrupt_company_stops_trading():
    _, company = founded_player()
    engine = make_engine()
    company.register(engine)
    company.declare_bankruptcy(day=1)
    cash = company.finances.cash
    engine.run_days(60)
    assert company.finances.cash == cash


def test_refounding_requires_the_configured_net_worth():
    # The project manager's rule: $500,000 personal net worth after a failure.
    player, company = founded_player()
    company.declare_bankruptcy(day=10)
    allowed, reason = player.can_found_company()
    assert not allowed
    assert "500,000" in reason

    player.cash = Money(600_000)
    allowed, _ = player.can_found_company()
    assert allowed
    replacement, _ = player.found_company("Second Chance", day=11)
    assert replacement is not None
    assert player.former_companies == ["Test Capital"]


def test_company_bankruptcy_does_not_end_the_playthrough():
    # V1.13 / V2.12: only personal bankruptcy ends the game.
    player, company = founded_player()
    company.declare_bankruptcy(day=10)
    assert not player.is_personally_bankrupt()


def test_personal_bankruptcy_is_the_game_ending_condition():
    player = Player("Unlucky", cash=Money(-250_000))
    assert player.is_personally_bankrupt()
    assert Player("Fine", cash=Money(-249_999)).is_personally_bankrupt() is False


def test_net_worth_combines_personal_cash_and_company_value():
    player, company = founded_player()
    assert player.net_worth() == player.cash + company.value()
    company.declare_bankruptcy(day=2)
    # A failed company contributes nothing.
    assert player.net_worth() == player.cash


# -- statistics and persistence -------------------------------------------


def test_company_statistics_cover_volume_3_13():
    _, company = founded_player()
    stats = company.statistics()
    for key in ("Company Value", "Cash", "Net Worth", "Weekly Profit",
                "Reputation", "Company Level", "Employees", "Debt"):
        assert key in stats
    assert isinstance(stats["Reputation"], Percentage)


def test_player_state_round_trip():
    player, company = founded_player()
    economy, banking = build_banking()
    economy.health = 0.5
    terms = banking.best_offer(company_value=Money(1_000_000), reputation=0.9)
    company.take_loan(terms, Money(60_000), day=1, allocator=IdAllocator())
    engine = make_engine()
    company.register(engine)
    engine.run_days(90)

    saved = player.state()
    restored = Player("placeholder")
    restored.restore(saved)

    assert restored.name == player.name
    assert restored.cash == player.cash
    assert restored.company is not None
    assert restored.company.name == company.name
    assert restored.company.finances.cash == company.finances.cash
    assert restored.company.reputation == company.reputation
    assert restored.company.loans.total_outstanding() == company.loans.total_outstanding()
    assert restored.company.finances.ledger.lifetime.profit == company.finances.lifetime_profit


def test_player_state_round_trip_without_a_company():
    player = Player("Solo")
    restored = Player("placeholder")
    restored.restore(player.state())
    assert restored.company is None
    assert restored.cash == player.cash
