"""Console commands that move money and the clock."""

from __future__ import annotations

import pytest
from console_support import _finish, found_company, run

from apex_horizon.engine.values import Money

# -- money (the specified syntax) -----------------------------------------


def test_money_player_reports_the_cash_the_game_is_using(game):
    game.context.player.cash = Money("1234.50")

    assert "$1,234.50" in run(game, "money player")


def test_money_player_add_changes_the_real_cash(game):
    before = game.context.player.cash

    run(game, "money player add 1000")

    assert game.context.player.cash == before + Money(1_000)


def test_money_player_remove_and_set(game):
    run(game, "money player set 500")
    assert game.context.player.cash == Money(500)

    run(game, "money player remove 200")
    assert game.context.player.cash == Money(300)


def test_money_accepts_decimals(game):
    run(game, "money player set 12.34")

    assert game.context.player.cash == Money("12.34")


def test_money_accepts_the_way_a_person_writes_it(game):
    run(game, "money player set $1,250.75")

    assert game.context.player.cash == Money("1250.75")


def test_company_money_says_so_when_there_is_no_company(game):
    reply = run(game, "money company add 1000")

    assert reply == "No company currently exists."
    assert not reply.ok


def test_company_money_moves_the_company_cash(game):
    found_company(game)
    before = game.context.company.finances.cash

    run(game, "money company add 5000")

    assert game.context.company.finances.cash == before + Money(5_000)


def test_company_money_is_recorded_rather_than_conjured(game):
    """It goes through the company's books, so the ledger stays truthful."""
    found_company(game)
    entries = len(game.context.company.finances.ledger.entries)

    run(game, "money company add 5000")
    run(game, "money company remove 2000")

    assert len(game.context.company.finances.ledger.entries) == entries + 2


def test_company_money_set_lands_on_the_number_asked_for(game):
    found_company(game)

    run(game, "money company set 750.25")

    assert game.context.company.finances.cash == Money("750.25")


def test_personal_and_company_money_stay_separate(game):
    """V1.4, V3.4: two financial systems the console must not merge."""
    found_company(game)
    personal = game.context.player.cash

    run(game, "money company add 9000")

    assert game.context.player.cash == personal


def test_a_bad_money_amount_is_refused_without_changing_anything(game):
    before = game.context.player.cash

    reply = run(game, "money player add banana")

    assert not reply.ok
    assert game.context.player.cash == before


def test_a_negative_add_points_at_the_right_command(game):
    reply = run(game, "money player add -50")

    assert not reply.ok
    assert "remove" in reply


# -- time ------------------------------------------------------------------


def test_time_reports_the_calendar_format(game):
    reply = run(game, "time")

    assert reply == "It is Year 1, Month 1, Week 1, Day 1."


def test_time_add_advances_the_simulation_itself(game):
    """Not a label: the engine must live through every one of those days."""
    before = game.context.engine.date.day

    run(game, "time add 3day")
    _finish(game)

    assert game.context.engine.date.day == before + 3
    assert game.context.engine.tick >= 3


@pytest.mark.parametrize(
    ("command", "days"),
    [("time add 4day", 4), ("time add 3week", 21), ("time add 2month", 56),
     ("time add 1year", 336)],
)
def test_every_unit_moves_the_right_number_of_days(game, command, days):
    before = game.context.engine.date.day

    run(game, command)
    _finish(game)

    assert game.context.engine.date.day == before + days


def test_time_set_lands_on_the_date_asked_for(game):
    run(game, "time set 2 3 2 4")
    _finish(game)

    date = game.context.engine.date
    assert (date.year(), date.month(), date.week_of_month(), date.day_of_week()) == (
        2, 3, 2, 4
    )


def test_time_will_not_go_backwards(game):
    run(game, "time add 2month")
    _finish(game)
    before = game.context.engine.date.day

    reply = run(game, "time set 1 1 1 1")

    assert not reply.ok
    assert "forwards" in reply
    assert game.context.engine.date.day == before


def test_a_date_outside_the_calendar_is_refused(game):
    reply = run(game, "time set 2 13 1 1")

    assert not reply.ok
    assert "month" in reply


def test_a_long_jump_is_spread_across_frames(game):
    """A year takes seconds to simulate; the window must keep drawing."""
    run(game, "time add 1year")

    assert game.dev_commands.busy
    game.dev_commands.pump(0.01)
    assert 0 < game.dev_commands.pending_days < 336


def test_a_jump_can_be_abandoned(game):
    run(game, "time add 5year")

    assert run(game, "time cancel").startswith("Abandoned")
    assert not game.dev_commands.busy


def test_an_absurd_jump_is_refused_rather_than_attempted(game):
    reply = run(game, "time add 500year")

    assert not reply.ok
    assert not game.dev_commands.busy
