"""The ledger, founding a company, and keeping its money separate."""

from __future__ import annotations

import pytest
from company_support import founded_player

from apex_horizon.engine.company import (
    ExpenseCategory,
    Ledger,
    Player,
    RevenueCategory,
)
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money

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


def test_a_new_player_has_no_company_and_may_not_yet_found_one():
    """The opening of the game: an individual investor, not a CEO (V1.19).

    Two things stand between the player and a company, in this order: the
    Create Company unlock (V6.4), and then the founding cost (V3.3).
    """
    player = Player("New Owner")
    assert player.cash == Money(10_000)
    assert player.company is None

    allowed, reason = player.can_found_company()
    assert not allowed
    assert "Create Company" in reason, "the unlock is the first gate"


def test_the_unlock_alone_does_not_make_a_company_affordable():
    # V1.2 gives $10,000; the project manager set founding at $25,000, so even
    # once Create Company is unlocked the player must build capital first.
    player = Player("New Owner")
    player.unlocks.unlock(CREATE_COMPANY)

    allowed, reason = player.can_found_company()
    assert not allowed
    assert "25,000" in reason


def test_unlocking_create_company_does_not_create_a_company():
    """The unlock is permission; founding is a separate decision (V3.3)."""
    player = Player("New Owner", cash=Money(40_000))
    player.unlocks.unlock(CREATE_COMPANY)

    assert player.company is None
    assert player.can_found_company()[0]


def test_founding_deducts_the_cost_and_capitalises_the_company():
    player = Player("Owner", cash=Money(40_000))
    player.unlocks.unlock(CREATE_COMPANY)
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
