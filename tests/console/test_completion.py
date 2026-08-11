"""The console's context-aware suggestions, and its text cursor.

The suggestions are derived from the command table's own declared syntax, so
these tests lean on that being the single source: they assert against real
commands and real unlock keys rather than against a fixture grammar.
"""

from __future__ import annotations

import pygame
import pytest
from console_support import key

from apex_horizon.debug.completion import CommandGrammar
from apex_horizon.ui.console import ConsoleOverlay


@pytest.fixture
def grammar(game):
    return CommandGrammar(game.dev_commands)


@pytest.fixture
def console(game):
    overlay = ConsoleOverlay(game.dev_commands)
    overlay.show()
    return overlay


def texts(suggestions):
    return [item.text for item in suggestions]


def typed(console, text: str) -> None:
    """Type each character through the real key handler."""
    for character in text:
        console.handle_event(key(ord(character), 0, character))


# -- the grammar -----------------------------------------------------------


def test_a_top_level_prefix_narrows_to_matching_commands(grammar):
    assert "money" in texts(grammar.suggest("m"))
    assert texts(grammar.suggest("mo")) == ["money"]
    assert "unlock" in texts(grammar.suggest("un"))


def test_a_command_offers_only_its_own_next_words(grammar):
    assert texts(grammar.suggest("money ")) == ["company", "player"]
    # Nothing from any other command leaks in at this position.
    assert "time" not in texts(grammar.suggest("money "))
    assert "status" not in texts(grammar.suggest("money "))


def test_partial_subcommands_narrow(grammar):
    assert texts(grammar.suggest("money p")) == ["player"]
    assert texts(grammar.suggest("money c")) == ["company"]
    assert texts(grammar.suggest("money player a")) == ["add"]


def test_both_targets_offer_the_same_actions(grammar):
    assert texts(grammar.suggest("money player ")) == ["add", "remove", "set"]
    assert texts(grammar.suggest("money company ")) == ["add", "remove", "set"]


def test_an_argument_position_offers_the_argument_and_nothing_else(grammar):
    suggestions = grammar.suggest("money player add ")
    assert texts(suggestions) == ["{amount}"]
    assert suggestions[0].placeholder
    assert not suggestions[0].acceptable, "a placeholder is a note, not a completion"


def test_an_impossible_position_suggests_nothing(grammar):
    assert grammar.suggest("nonsense ") == []
    assert grammar.suggest("money player add 5000 ") == []


def test_unlock_names_come_from_the_live_catalogue(game, grammar):
    keys = {unlock.key for unlock in game.context.unlocks.all}
    offered = set(texts(grammar.suggest("unlock add ")))

    assert keys <= offered, "every unlock in the catalogue should be offered"
    assert "all" in offered, "and the literal 'all' the syntax also allows"
    # The removed unlock must not linger in a second, stale list.
    assert "employees" not in offered
    assert texts(grammar.suggest("unlock add better_employees_")) == [
        "better_employees_1", "better_employees_2", "better_employees_3",
    ]


def test_time_commands_are_understood(grammar):
    assert texts(grammar.suggest("time ")) == ["add", "cancel", "set"]
    assert texts(grammar.suggest("time set ")) == ["{year}"]
    # 'time add' takes an amount carrying a unit, so once a number is typed the
    # units are the completions.
    assert texts(grammar.suggest("time add ")) == ["{amount}{unit}"]
    assert texts(grammar.suggest("time add 5")) == ["5day", "5month", "5week", "5year"]


def test_a_choice_of_literals_is_offered_as_the_literals(grammar):
    assert texts(grammar.suggest("event ")) == ["down", "up"]


def test_suggestions_follow_the_cursor_not_the_end_of_the_line(grammar):
    # Cursor sitting right after "money p", with more text beyond it.
    assert texts(grammar.suggest("money p add 500", cursor=7)) == ["player"]


# -- the console's use of it ----------------------------------------------


def test_suggestions_update_as_the_player_types(console):
    typed(console, "m")
    assert "money" in texts(console.suggestions)
    typed(console, "oney ")
    assert texts(console.suggestions) == ["company", "player"]


def test_arrow_keys_move_the_selection_and_highlight_it(console):
    typed(console, "money ")
    assert console.suggestion_index == 0
    assert console.selected_suggestion.text == "company"

    console.handle_event(key(pygame.K_DOWN))
    assert console.selected_suggestion.text == "player"
    console.handle_event(key(pygame.K_UP))
    assert console.selected_suggestion.text == "company"


def test_tab_accepts_the_selection_without_running_anything(console):
    typed(console, "money p")
    before = list(console.lines)

    console.handle_event(key(pygame.K_TAB))

    assert console.text == "money player "
    assert console.cursor == len(console.text)
    assert console.lines == before, "Tab must not execute the command"


def test_tab_completes_the_selected_suggestion_not_the_first(console):
    typed(console, "money ")
    console.handle_event(key(pygame.K_DOWN))  # company -> player
    console.handle_event(key(pygame.K_TAB))
    assert console.text == "money player "


def test_clicking_a_suggestion_behaves_exactly_as_tab_does(console, game):
    typed(console, "money ")
    surface = pygame.Surface((1100, 680))
    console.draw(surface, game.fonts, 0)
    assert console._suggestion_rects, "the list must be on screen to be clicked"

    rect, _index = console._suggestion_rects[1]
    before = list(console.lines)
    console.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=rect.center))

    assert console.text == "money player "
    assert console.lines == before, "clicking must not execute the command"


def test_a_placeholder_cannot_be_accepted(console):
    typed(console, "money player add ")
    before = console.text
    console.handle_event(key(pygame.K_TAB))
    assert console.text == before, "there is nothing to insert for {amount}"


def test_a_number_can_simply_be_typed_and_run(console, game):
    typed(console, "money player set 4321")
    console.handle_event(key(pygame.K_RETURN, 0, "\r"))
    assert game.context.player.cash.format(decimals=0) == "$4,321"


def test_command_history_still_works_on_an_empty_line(console):
    typed(console, "status")
    console.handle_event(key(pygame.K_RETURN, 0, "\r"))
    assert console.text == ""

    # Nothing typed, so the arrows belong to the history as they always did.
    console.handle_event(key(pygame.K_UP))
    assert console.text == "status"
    console.handle_event(key(pygame.K_DOWN))
    assert console.text == ""


# -- the cursor ------------------------------------------------------------


def test_the_cursor_follows_what_is_typed(console):
    typed(console, "money")
    assert console.cursor == 5


def test_the_cursor_moves_and_inserts_where_it_sits(console):
    typed(console, "money player")
    for _ in range(len("player")):
        console.handle_event(key(pygame.K_LEFT))
    assert console.cursor == len("money ")

    console.handle_event(key(pygame.K_BACKSPACE))
    assert console.text == "moneyplayer"
    assert console.cursor == 5

    console.handle_event(key(ord(" "), 0, " "))
    assert console.text == "money player"
    assert console.cursor == 6


def test_home_and_end_reach_both_ends(console):
    typed(console, "money player")
    console.handle_event(key(pygame.K_HOME))
    assert console.cursor == 0
    console.handle_event(key(pygame.K_END))
    assert console.cursor == len("money player")


def test_delete_removes_the_character_under_the_cursor(console):
    typed(console, "money")
    console.handle_event(key(pygame.K_HOME))
    console.handle_event(key(pygame.K_DELETE))
    assert console.text == "oney"
    assert console.cursor == 0


def test_completing_inserts_at_the_cursor_rather_than_the_end(console):
    """The cursor is inside the line, so the word under it is what completes —
    what follows must be left alone rather than appended to."""
    console.set_text("money p add 500", cursor=len("money p"))
    console.handle_event(key(pygame.K_TAB))
    assert console.text == "money player add 500"
    assert console.cursor == len("money player ")


def test_the_cursor_blinks(console):
    on = console.cursor_visible(0)
    off = console.cursor_visible(800)
    assert on and not off, "it has to be visible sometimes and not others"
    assert console.cursor_visible(1100), "and come back round again"
