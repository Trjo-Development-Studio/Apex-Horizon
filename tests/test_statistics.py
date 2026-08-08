"""Tests for statistics and the developer console (V28, V15.18)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.statistics import LifetimeStatistics
from apex_horizon.engine.values import Calendar, Money, set_calendar


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


# -- lifetime statistics (V28.7) ------------------------------------------


def test_counters_start_at_nothing():
    stats = LifetimeStatistics()

    assert stats.employees_hired == 0
    assert stats.total_profit.is_zero
    assert stats.net_lifetime_profit().is_zero


def test_profit_and_losses_are_recorded_separately():
    """V28.7 asks for totals, and a total that nets out hides the scale."""
    stats = LifetimeStatistics()

    stats.record_closed_position(Money(500))
    stats.record_closed_position(Money(-200))

    assert stats.total_profit == Money(500)
    assert stats.total_losses == Money(200)
    assert stats.net_lifetime_profit() == Money(300)
    assert stats.positions_closed == 2


def test_high_water_marks_only_rise():
    """V28.7: 'the most you have ever been worth' cannot fall."""
    stats = LifetimeStatistics()

    stats.observe(net_worth=Money(1_000), company_value=Money(500))
    stats.observe(net_worth=Money(400), company_value=Money(100))

    assert stats.highest_net_worth == Money(1_000)
    assert stats.highest_company_value == Money(500)


def test_records_survive_losing_a_company():
    """The counters describe the playthrough, not the current company."""
    stats = LifetimeStatistics()
    stats.record_founding()
    stats.record_hire()
    stats.record_hire()
    stats.record_closed_position(Money(900))

    stats.record_bankruptcy()
    stats.record_founding()

    assert stats.companies_founded == 2
    assert stats.companies_lost == 1
    assert stats.employees_hired == 2, "hires from the lost company still count"
    assert stats.total_profit == Money(900)


def test_a_summary_answers_questions_a_player_would_ask():
    """V28.8: statistics serve judgment rather than exist for their own sake."""
    stats = LifetimeStatistics()
    summary = stats.summary()

    assert "Employees ever hired" in summary
    assert "Companies acquired" in summary
    assert "Highest net worth" in summary


def test_statistics_survive_a_round_trip():
    stats = LifetimeStatistics()
    stats.record_hire()
    stats.record_closed_position(Money(1_500))
    stats.observe(net_worth=Money(9_000))

    restored = LifetimeStatistics()
    restored.restore(stats.state())

    assert restored.employees_hired == 1
    assert restored.total_profit == Money(1_500)
    assert restored.highest_net_worth == Money(9_000)
    assert restored.summary() == stats.summary()


# -- the developer console (V15.18) ---------------------------------------


@pytest.fixture
def game():
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from apex_horizon.ui.app import GameApp

    set_calendar(Calendar(7, 4, 12))
    app = GameApp(size=(900, 600), seed=2026)
    yield app
    app.shutdown()


def test_the_console_is_inert_without_a_terminal(game):
    """Tests and CI have no terminal, so it must never try to read one."""
    assert not game.console.available
    assert not game.console.start()


def test_every_capability_volume_15_18_names_exists(game):
    """Money, time, employees, research, market events, the economy."""
    assert {"money", "days", "hire", "research", "event", "economy"} <= set(
        game.console.commands
    )


def test_giving_money_gives_money(game):
    before = game.context.player.cash

    game.console.execute("money 5000")

    assert game.context.player.cash == before + Money(5_000)


def test_advancing_time_advances_time(game):
    before = game.context.engine.date.day

    game.console.execute("days 10")

    assert game.context.engine.date.day == before + 10


def test_a_market_event_moves_every_price(game):
    listing = game.context.market.active_listings()[0]
    before = listing.price

    game.console.execute("event up 10")

    assert listing.price > before


def test_the_economy_can_be_set(game):
    game.console.execute("economy -0.9")

    assert game.context.economy.health == pytest.approx(-0.9)


def test_unlocking_applies_the_effects(game):
    """A granted unlock must actually change the game, not just be recorded."""
    game.console.execute("unlock all")

    assert game.context.news.enabled
    assert game.context.analytics.enabled


def test_an_unknown_command_is_reported_rather_than_raised(game):
    assert "Unknown command" in game.console.execute("wat")


def test_a_bad_argument_never_ends_the_game(game):
    """V15.18 is a debugging tool; a typo must not take the game down."""
    result = game.console.execute("money not-a-number")

    assert "failed" in result.lower()
    assert game.context.engine is not None


def test_wrong_arity_reports_usage(game):
    assert "Usage:" in game.console.execute("money")


def test_lines_typed_at_a_terminal_run_on_the_main_thread(game):
    """The reader thread only queues; commands run when the app polls.

    That separation is what stops a command changing the world halfway through
    a frame, so it is worth testing rather than assuming.
    """
    import io
    import sys
    import time

    class FakeTerminal(io.StringIO):
        def isatty(self) -> bool:
            return True

    before = game.context.player.cash
    real, sys.stdin = sys.stdin, FakeTerminal("money 1234\n")
    try:
        assert game.console.start()
        time.sleep(0.3)
        # Nothing has happened yet: the line is queued, not executed.
        assert game.context.player.cash == before

        game.console.poll()
        assert game.context.player.cash == before + Money(1_234)
    finally:
        game.console.stop()
        sys.stdin = real
