"""Tests for the developer console (V15.18, and the project manager's brief).

The console exists to change a running game, so almost every test here asserts
against the *game* rather than against the sentence the console printed: cash
the simulation would spend, days the engine actually lived through, unlocks the
effects system has already acted on. A command that only produced convincing
output would pass a test of its wording and fail every one of these.
"""

from __future__ import annotations

import os

import pygame
import pytest

from apex_horizon.debug.commands import DeveloperCommands, Reply
from apex_horizon.engine.unlocks import catalogue as c
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.ui.console import COMMAND, ERROR, ConsoleOverlay, opens_console


@pytest.fixture
def game():
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    from apex_horizon.ui.app import GameApp

    set_calendar(Calendar(7, 4, 12))
    app = GameApp(size=(1100, 700), seed=2026)
    yield app
    app.shutdown()
    set_calendar(None)


def run(game, line: str) -> Reply:
    return game.dev_commands.execute(line)


def key(code, mod=0, unicode=""):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod, unicode=unicode)


def type_line(console, text: str) -> None:
    for character in text:
        console.handle_event(key(ord(character), 0, character))
    console.handle_event(key(pygame.K_RETURN, 0, "\r"))


def found_company(game) -> None:
    player = game.context.player
    player.unlocks.unlock(c.CREATE_COMPANY)
    player.cash = Money(100_000)
    company, message = player.found_company("Test Capital", day=1)
    assert company is not None, message


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


# -- unlocks ---------------------------------------------------------------


def test_unlocks_lists_what_is_owned(game):
    reply = run(game, "unlocks")

    assert "basic_investing" in reply
    assert "create_company" not in reply


def test_unlock_add_uses_the_real_unlock_state(game):
    """The unlock and the money it needs both come from the console."""
    run(game, "unlock add create_company")
    run(game, "money player set 100000")

    assert game.context.player.unlocks.has(c.CREATE_COMPANY)
    assert game.context.player.can_found_company()[0]


def test_unlock_add_accepts_the_name_shown_in_the_interface(game):
    run(game, "unlock add Create Company")

    assert game.context.player.unlocks.has(c.CREATE_COMPANY)


def test_unlock_add_grants_what_the_unlock_requires(game):
    """V6.9 makes progression sequential; a stranded node is not a game state."""
    run(game, "unlock add better_analytics_2")

    tree = game.context.player.unlocks
    assert tree.has(c.BASIC_ANALYTICS) and tree.has(c.BETTER_ANALYTICS_1)


def test_unlock_add_applies_the_effects(game):
    """A granted unlock must change the game, not merely be recorded."""
    run(game, "unlock add breaking_news")

    assert game.context.news.enabled


def test_unlock_remove_takes_the_effects_away_again(game):
    run(game, "unlock add breaking_news")

    run(game, "unlock remove basic_news")

    assert not game.context.news.enabled
    assert not game.context.player.unlocks.has(c.BREAKING_NEWS)


def test_unlock_remove_reports_what_it_had_to_take_with_it(game):
    run(game, "unlock add better_analytics_2")

    reply = run(game, "unlock remove basic_analytics")

    assert "Better Analytics 1" in reply and "Better Analytics 2" in reply


def test_the_starting_unlock_cannot_be_removed(game):
    reply = run(game, "unlock remove basic_investing")

    assert not reply.ok
    assert game.context.player.unlocks.has(c.BASIC_INVESTING)


def test_an_unknown_unlock_is_named_in_the_error(game):
    reply = run(game, "unlock add teleportation")

    assert reply == "Unknown unlock: teleportation"
    assert not reply.ok


# -- help ------------------------------------------------------------------


def test_help_lists_every_command(game):
    reply = run(game, "help")

    for name in game.dev_commands.commands:
        assert name in reply


@pytest.mark.parametrize(
    ("topic", "expected"),
    [("money", "money player set {amount}"),
     ("time", "time set {year} {month} {week} {day}"),
     ("unlocks", "unlock add {unlock_name}")],
)
def test_help_shows_the_exact_syntax(game, topic, expected):
    assert expected in run(game, f"help {topic}")


def test_help_for_something_that_is_not_a_topic(game):
    reply = run(game, "help teleportation")

    assert not reply.ok
    assert "Topics:" in reply


# -- malformed input -------------------------------------------------------


@pytest.mark.parametrize("line", [
    "wat", "money", "money bank add 5", "money player", "money player add",
    "money player add 1 2 3", "time", "time set", "time set a b c d",
    "time add", "time add 5fortnights", "unlock", "unlock add", "unlocks all",
    "unlock remove", "help", "", "   ", "money player set 1e999",
    "unlock add " + "x" * 500,
])
def test_no_input_can_end_the_game(game, line):
    """Every one of these must produce a sentence, not an exception (V15.18)."""
    reply = game.dev_commands.execute(line)

    assert isinstance(reply, str)
    assert game.context.engine is not None


def test_an_unknown_command_says_so(game):
    reply = run(game, "teleport")

    assert reply.startswith("Unknown command: teleport")
    assert not reply.ok


# -- the in-game console (Ctrl+T) -----------------------------------------


def test_ctrl_t_opens_and_closes_it(game):
    assert not game.dev_console.open

    game.handle_events()
    pygame.event.post(key(pygame.K_t, pygame.KMOD_CTRL, "t"))
    game.handle_events()
    assert game.dev_console.open

    pygame.event.post(key(pygame.K_t, pygame.KMOD_CTRL, "t"))
    game.handle_events()
    assert not game.dev_console.open


def test_plain_t_does_not_open_it(game):
    assert not opens_console(key(pygame.K_t, 0, "t"))


def test_escape_closes_it(game):
    game.dev_console.show()

    game.dev_console.handle_event(key(pygame.K_ESCAPE))

    assert not game.dev_console.open


def test_the_opening_shortcut_does_not_type_itself(game):
    pygame.event.post(key(pygame.K_t, pygame.KMOD_CTRL, "t"))
    game.handle_events()

    assert game.dev_console.text == ""


def test_typing_reaches_the_console_and_not_the_game(game):
    """It captures the keyboard, so a speed shortcut cannot fire underneath."""
    game.dev_console.show()
    speed = game.context.engine.clock.speed

    pygame.event.post(key(pygame.K_2, 0, "2"))
    game.handle_events()

    assert game.dev_console.text == "2"
    assert game.context.engine.clock.speed == speed


def test_a_typed_command_changes_the_game(game):
    game.dev_console.show()
    before = game.context.player.cash

    type_line(game.dev_console, "money player add 250")

    assert game.context.player.cash == before + Money(250)


def test_the_command_is_shown_apart_from_its_output(game):
    game.dev_console.show()

    type_line(game.dev_console, "money player")

    assert game.dev_console.lines[-2][1] == COMMAND
    assert game.dev_console.lines[-2][0].startswith("> money player")
    assert game.dev_console.lines[-1][1] != COMMAND


def test_an_error_is_shown_as_one(game):
    game.dev_console.show()

    type_line(game.dev_console, "nonsense")

    assert game.dev_console.lines[-1][1] == ERROR


def test_backspace_and_history_work_as_a_console_should(game):
    console = game.dev_console
    console.show()
    type_line(console, "time")

    console.handle_event(key(pygame.K_UP))
    assert console.text == "time"
    console.handle_event(key(pygame.K_BACKSPACE))
    assert console.text == "tim"


def test_it_pauses_the_simulation_while_open(game):
    """V13.20: state being read should not move underneath the reader."""
    game.dev_console.show()

    game.tick()

    assert game.context.engine.clock.paused


def test_closing_it_lets_the_game_run_again(game):
    game.dev_console.show()
    game.tick()

    game.dev_console.hide()
    game.tick()

    assert not game.context.engine.clock.paused


def test_a_finished_time_jump_reports_itself_in_the_console(game):
    console = game.dev_console
    console.show()
    type_line(console, "time add 2day")

    _finish(game)

    assert "Time is now" in console.lines[-1][0]


def test_the_overlay_draws_without_a_game_behind_it(game):
    """Drawing is the one thing that must survive any state at all."""
    console = ConsoleOverlay(DeveloperCommands(game.context))
    console.show()
    console.write("x" * 400)
    surface = pygame.Surface((640, 480))

    console.draw(surface, game.fonts, 0)

    assert surface.get_at((320, 240))[:3] != (0, 0, 0)


def test_both_consoles_speak_the_same_language(game):
    """One command table, two ways in — a command cannot exist in only one."""
    assert game.console.commands is game.dev_commands.commands
    assert game.dev_console.commands is game.dev_commands


def test_the_terminal_console_is_inert_without_a_terminal(game):
    assert not game.console.available
    assert not game.console.start()


def _finish(game) -> None:
    """Run any scheduled time jump to completion, as frames would."""
    for _ in range(2_000):
        if not game.dev_commands.busy:
            return
        game.dev_commands.pump(0.05)
    raise AssertionError("the scheduled jump never finished")


def test_a_console_change_counts_as_an_unsaved_change(game):
    """V16.23: the save indicator must not claim everything is saved."""
    game.saves.unsaved_changes = False

    run(game, "money player add 100")

    assert game.saves.unsaved_changes


def test_reading_does_not_count_as_a_change(game):
    game.saves.unsaved_changes = False

    run(game, "help")
    run(game, "money player")
    run(game, "unlocks")

    assert not game.saves.unsaved_changes
