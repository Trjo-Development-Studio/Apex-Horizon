"""Tests for the company and its finances (Design Bible Volumes 3 and 17)."""

from __future__ import annotations

from random import Random

import pytest

from apex_horizon.engine.company import (
    ExpenseCategory,
    Ledger,
    PeriodTotals,
    Player,
    PlayerCompany,
    RevenueCategory,
)
from apex_horizon.engine.economy import BankingSystem, EconomySystem
from apex_horizon.engine.simulation import SimulationClock, SimulationEngine
from apex_horizon.engine.values import Calendar, IdAllocator, Money, Percentage, set_calendar
from apex_horizon.engine.world import generate_world


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


def make_engine(seed: int = 1) -> SimulationEngine:
    clock = SimulationClock(
        seconds_per_day=1.0, speed=1, speed_options=(1,), max_days_per_update=100_000
    )
    return SimulationEngine(clock=clock, seed=seed)


def founded_player(cash: int = 100_000) -> tuple[Player, PlayerCompany]:
    player = Player("Test Owner", cash=Money(cash))
    company, _ = player.found_company("Test Capital", day=1)
    return player, company


# -- the ledger (V17.27) ---------------------------------------------------


def test_every_total_is_derived_from_the_ledger():
    ledger = Ledger()
    ledger.record_revenue(1, RevenueCategory.DIVIDENDS, Money(500))
    ledger.record_expense(1, ExpenseCategory.SALARIES, Money(200))
    assert ledger.week.revenue == Money(500)
    assert ledger.week.expenses == Money(200)
    assert ledger.week.profit == Money(300)
    assert ledger.lifetime.profit == Money(300)


def test_negative_amounts_are_rejected():
    ledger = Ledger()
    with pytest.raises(ValueError):
        ledger.record_revenue(1, RevenueCategory.DIVIDENDS, Money(-1))


def test_closing_a_period_resets_only_that_period():
    ledger = Ledger()
    ledger.record_revenue(1, RevenueCategory.DIVIDENDS, Money(100))
    closed = ledger.close_week()
    assert closed.revenue == Money(100)
    assert ledger.week.revenue.is_zero
    # Longer periods and lifetime totals are untouched.
    assert ledger.month.revenue == Money(100)
    assert ledger.lifetime.revenue == Money(100)


def test_monthly_summaries_preserve_history_within_bounds():
    ledger = Ledger()
    for month in range(300):
        ledger.record_revenue(month, RevenueCategory.DIVIDENDS, Money(10))
        ledger.close_month(month)
    assert len(ledger.monthly_summaries) == ledger.MAX_MONTHLY_SUMMARIES
    # Lifetime totals survive even though individual entries are trimmed.
    assert ledger.lifetime.revenue == Money(3000)


def test_entries_are_bounded_but_totals_are_not():
    ledger = Ledger()
    for day in range(ledger.MAX_ENTRIES + 500):
        ledger.record_expense(day, ExpenseCategory.OPERATIONAL, Money(1))
    assert len(ledger.entries) == ledger.MAX_ENTRIES
    assert ledger.lifetime.expenses == Money(ledger.MAX_ENTRIES + 500)


def test_breakdowns_are_sorted_and_separated():
    ledger = Ledger()
    ledger.record_expense(1, ExpenseCategory.SALARIES, Money(900))
    ledger.record_expense(1, ExpenseCategory.OPERATIONAL, Money(100))
    ledger.record_revenue(1, RevenueCategory.DIVIDENDS, Money(50))
    expenses = ledger.expense_breakdown()
    assert list(expenses) == ["Salaries", "Operational costs"]
    assert list(ledger.revenue_breakdown()) == ["Dividend income"]


# -- founding (V2.4, V3.3) -------------------------------------------------


def test_starting_player_cannot_immediately_afford_a_company():
    # V1.2 gives $10,000; the project manager set founding at $25,000, so the
    # player must build capital first.
    player = Player("New Owner")
    assert player.cash == Money(10_000)
    allowed, reason = player.can_found_company()
    assert not allowed
    assert "25,000" in reason


def test_founding_deducts_the_cost_and_capitalises_the_company():
    player = Player("Owner", cash=Money(40_000))
    company, message = player.found_company("Horizon Capital", day=1)
    assert company is not None
    assert player.cash == Money(15_000)
    assert company.finances.cash == Money(25_000)
    assert "founded" in message.lower()
    # The founding capital is recorded, not conjured (V17.27) — but as
    # financing, not as revenue: the company received it, it did not earn it.
    assert company.finances.ledger.lifetime.revenue.is_zero
    assert company.finances.ledger.cash_in == Money(25_000)


def test_only_one_company_at_a_time():
    player, _ = founded_player()
    allowed, reason = player.can_found_company()
    assert not allowed
    assert "already run" in reason


def test_company_starts_at_level_one_with_its_capacity():
    _, company = founded_player()
    assert company.level == 1
    assert company.employee_capacity == 10
    company.set_level(3)
    assert company.employee_capacity == 50
    company.set_level(99)
    assert company.level == company.max_level
    assert company.employee_capacity == 200


# -- personal versus company money (V1.4, V3.4) ---------------------------


def test_personal_cash_can_move_into_the_company():
    player, company = founded_player()
    ok, _ = player.transfer_to_company(Money(10_000), day=2)
    assert ok
    assert player.cash == Money(65_000)
    assert company.finances.cash == Money(35_000)


def test_there_is_no_way_to_move_company_money_back():
    # V1.4 permits personal -> company only. The absence of a reverse operation
    # is the enforcement.
    player, _ = founded_player()
    assert not hasattr(player, "transfer_from_company")
    assert not any("withdraw" in name.lower() for name in dir(player))


def test_transfers_are_validated():
    player, _ = founded_player()
    assert player.transfer_to_company(Money(10_000_000), day=2)[0] is False
    assert player.transfer_to_company(Money(0), day=2)[0] is False
    lonely = Player("No Company")
    assert lonely.transfer_to_company(Money(1), day=2)[0] is False


# -- profit, assets and value (V17.6 - V17.12) ----------------------------


def test_profit_is_revenue_minus_expenses():
    _, company = founded_player()
    company.finances.receive(1, RevenueCategory.INVESTMENT_PROFIT, Money(5_000))
    company.finances.spend(1, ExpenseCategory.SALARIES, Money(2_000))
    assert company.finances.profit_this_week == Money(3_000)
    assert company.finances.cash == Money(28_000)


def test_assets_include_holdings_owned_by_other_systems():
    _, company = founded_player()
    company.finances.register_asset_provider("investments", lambda: Money(50_000))
    assert company.finances.assets() == Money(75_000)
    assert company.finances.net_worth() == Money(75_000)


def test_liabilities_reduce_net_worth():
    _, company = founded_player()
    company.finances.register_liability_provider("other", lambda: Money(5_000))
    assert company.finances.net_worth() == Money(20_000)


def test_company_value_rewards_sustained_profit():
    _, company = founded_player()
    plain = company.value()
    company.finances.receive(1, RevenueCategory.INVESTMENT_PROFIT, Money(10_000))
    company.finances.close_year()
    assert company.value() > plain


def test_profit_margin_handles_no_revenue():
    _, company = founded_player()
    company.finances.ledger.lifetime.revenue = Money.zero()
    assert company.finances.profit_margin().is_zero


def test_financial_report_covers_the_required_figures():
    # V17.14 lists income, expenses, profit, assets, liabilities and net worth.
    _, company = founded_player()
    report = company.finances.report(company.level)
    for key in ("Cash", "Revenue (year)", "Expenses (year)", "Profit (year)",
                "Assets", "Liabilities", "Net Worth", "Company Value"):
        assert key in report


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
                "Reputation", "Company Level", "Employee Capacity", "Debt"):
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
