"""The Start Menu, choosing a slot, and the expandable sidebar."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from ui_support import _choose, _new_game, click

from apex_horizon.ui import theme
from apex_horizon.ui.popups import PromptPopup
from apex_horizon.ui.start_menu import NEW_GAME

# -- the Start Menu (V16.4) -----------------------------------------------


def test_the_game_opens_on_the_start_menu(menu_app):
    assert menu_app.in_menu
    menu_app.menu.draw(menu_app.surface, menu_app.fonts, (0, 0))


def test_a_directly_built_application_starts_in_play(app):
    """Tests and tools want a running game, not a menu."""
    assert not app.in_menu


def test_new_game_asks_for_a_slot_before_starting_one(menu_app):
    """PM: the player chooses where the game lives; nothing is picked for them."""

    menu_app.menu.request = NEW_GAME
    menu_app._menu_tick(0)

    assert menu_app.in_menu, "no world exists until a slot is chosen"
    assert menu_app.saves.slot is None


def test_choosing_an_empty_slot_asks_for_a_name(menu_app):

    menu_app.menu.request = (NEW_GAME, "2")
    menu_app._menu_tick(0)

    assert isinstance(menu_app.popups.current, PromptPopup)
    assert menu_app.in_menu, "still no world until the name is given"


def test_new_game_begins_a_world_in_the_chosen_slot(menu_app):
    _new_game(menu_app, slot="3", name="My Empire")

    assert not menu_app.in_menu
    assert menu_app.current_key == "dashboard"
    assert menu_app.context.market.active_listings()
    assert menu_app.saves.slot == "3"
    assert menu_app.saves.store.info("3").metadata.name == "My Empire"


def test_the_new_game_is_written_to_its_slot_immediately(menu_app):
    _new_game(menu_app, slot="4")

    assert menu_app.saves.store.info("4").exists
    assert not menu_app.saves.store.info("1").exists


def test_an_occupied_slot_is_never_overwritten_without_asking(menu_app):

    menu_app.saves.save_to_slot(2, "Someone else's game")

    menu_app.menu.request = (NEW_GAME, "2")
    menu_app._menu_tick(0)
    assert menu_app.popups.current is not None
    _choose(menu_app, "cancel")

    assert menu_app.in_menu
    assert menu_app.saves.store.info(2).metadata.name == "Someone else's game"


def test_confirming_the_overwrite_replaces_the_slot(menu_app):
    menu_app.saves.save_to_slot(2, "Someone else's game")

    _new_game(menu_app, slot="2", name="Mine now")

    assert not menu_app.in_menu
    assert menu_app.saves.store.info(2).metadata.name == "Mine now"


def test_the_autosave_writes_to_the_games_own_slot(menu_app):
    """PM: autosaving must never create a slot the player did not choose."""
    _new_game(menu_app, slot="5", name="Autosaved")
    menu_app.context.engine.run_days(30)

    menu_app.saves.record_playtime(menu_app.saves.autosave_interval_minutes * 60)

    occupied = [info.slot for info in menu_app.saves.slots() if info.exists]
    assert occupied == ["5"]
    assert menu_app.saves.store.info("5").metadata.name == "Autosaved"


def test_a_loaded_game_keeps_the_slot_it_came_from(menu_app):
    _new_game(menu_app, slot="3", name="Continued")
    menu_app.context.engine.run_days(10)
    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    menu_app._load_from_menu("3")

    assert not menu_app.in_menu
    assert menu_app.saves.slot == "3"
    assert menu_app.saves.metadata.name == "Continued"

    # And it keeps saving there, rather than drifting to another slot.
    menu_app.saves.record_playtime(menu_app.saves.autosave_interval_minutes * 60)
    assert [info.slot for info in menu_app.saves.slots() if info.exists] == ["3"]


def test_load_game_is_offered_only_once_something_is_saved(menu_app):
    assert menu_app.menu._saved_slots() == []

    menu_app.saves.save_to_slot(1)

    assert menu_app.menu._saved_slots()


def test_settings_opens_from_the_menu(menu_app):
    from apex_horizon.ui.start_menu import SETTINGS

    menu_app.menu.request = SETTINGS
    menu_app._menu_tick(0)

    assert not menu_app.in_menu
    assert menu_app.current_key == "settings"


def test_exit_game_ends_the_session(menu_app):
    from apex_horizon.ui.start_menu import EXIT

    menu_app.menu.request = EXIT
    menu_app._menu_tick(0)

    assert not menu_app.running


def test_save_and_exit_saves_then_returns_to_the_menu(menu_app):
    """V16.4 steps 1-5."""

    _new_game(menu_app, slot="1")
    menu_app.context.engine.run_days(20)

    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    assert menu_app.in_menu, "the player returns to the Main Menu"
    assert menu_app.running, "leaving a session is not leaving the game"
    assert menu_app.saves.store.info(menu_app.current_slot).exists


def test_a_failed_save_keeps_the_player_in_the_game(menu_app, monkeypatch):
    """V16.4 step 6: never pretend a save succeeded."""
    from apex_horizon.engine.save.service import SaveResult

    _new_game(menu_app, slot="1")

    monkeypatch.setattr(menu_app.saves, "save_to_slot",
                        lambda *a, **k: SaveResult(False, "Saving failed: disk full."))
    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    assert not menu_app.in_menu, "a failed save must not leave the session"
    assert menu_app.popups.is_open, "and must say so"


def test_loading_a_damaged_save_reports_rather_than_opening_it(menu_app, monkeypatch):
    from apex_horizon.engine.save.validation import LoadOutcome

    monkeypatch.setattr(menu_app.saves, "load_from_slot",
                        lambda *a, **k: LoadOutcome(None, ok=False,
                                                    problems=["That save is damaged."]))
    menu_app._load_from_menu("1")

    assert menu_app.in_menu
    assert "damaged" in menu_app.menu.message


# -- the expandable sidebar -----------------------------------------------


def test_the_sidebar_starts_open_with_the_names_showing(app):
    """Project manager, 2026-08-11: a first-time player should not have to
    work out what the icons mean. It opens at its full width rather than
    animating open on the first frame."""
    assert app.sidebar.expanded
    assert app.sidebar.width(0) == theme.SIDEBAR_EXPANDED


def test_clicking_the_logo_collapses_and_expands(app):
    app.draw(0)  # lay the logo out so it has a hit area
    logo = app.sidebar._logo_rect

    app.sidebar.handle_event(click(logo.center))
    assert not app.sidebar.expanded
    # The width eases closed over a couple of frames rather than jumping.
    app.sidebar.width(10_000)
    assert app.sidebar.width(11_000) == theme.SIDEBAR_WIDTH

    app.sidebar.handle_event(click(logo.center))
    assert app.sidebar.expanded
    app.sidebar.width(12_000)
    assert app.sidebar.width(13_000) == theme.SIDEBAR_EXPANDED
