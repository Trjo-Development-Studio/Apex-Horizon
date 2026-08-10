"""Autosaving, failure handling, and unsaved-change tracking."""

from __future__ import annotations

import pytest
from save_support import sample_document

from apex_horizon.engine.unlocks import CREATE_COMPANY

# -- autosaving (V16.5 - V16.7, V16.24) -----------------------------------


def test_the_game_autosaves_on_real_time(game):
    """PM decision: the interval is the player's own time, not the world's."""
    messages: list[str] = []
    game.saves.assign_slot(3, "Test Game")
    game.saves.on_autosave.append(messages.append)
    minutes = game.saves.autosave_interval_minutes
    assert minutes > 0

    # Time passing in the world alone must not trigger it.
    game.context.engine.run_days(400)
    assert not game.saves.store.info(3).exists

    game.saves.record_playtime(minutes * 60)
    assert game.saves.store.info(3).exists
    assert messages and messages[0] == "Autosaved"


def test_the_autosave_goes_to_the_slot_the_player_chose(game):
    """PM: a save has one slot, and autosaving is a save of that game."""
    game.saves.assign_slot(4, "Test Game")

    game.saves.record_playtime(game.saves.autosave_interval_minutes * 60)

    assert game.saves.store.info(4).exists
    others = [info.slot for info in game.saves.slots() if info.exists]
    assert others == ["4"], "no other slot may appear"
    assert not (game.saves.store.directory / "autosave.ahsave").exists()


def test_the_interval_is_not_reached_early(game):
    game.saves.assign_slot(1, "Test Game")

    game.saves.record_playtime(game.saves.autosave_interval_minutes * 60 - 1)

    assert not game.saves.store.info(1).exists


def test_each_autosave_replaces_the_last(game):
    minutes = game.saves.autosave_interval_minutes
    game.saves.assign_slot(2, "Test Game")
    game.saves.record_playtime(minutes * 60)
    first = game.saves.store.info(2).summary.day

    game.context.engine.run_days(60)
    game.saves.record_playtime(minutes * 60)

    second = game.saves.store.info(2).summary
    # The same file, replaced rather than accumulating.
    assert len(list(game.saves.store.directory.glob("*.ahsave"))) == 1
    assert second.day != first or second.month != 1


def test_a_game_with_no_slot_does_not_invent_one(game):
    game.saves.slot = None

    result = game.saves.autosave()

    assert not result.ok
    assert not any(info.exists for info in game.saves.slots())


def test_a_major_decision_autosaves_first(game):
    # V16.6: the moment before an irreversible decision is preserved.
    game.saves.assign_slot(5, "Test Game")

    result = game.saves.autosave_before("founding a company")

    assert result.ok
    assert game.saves.store.info(5).exists


def test_autosave_frequency_can_be_changed(game):
    """V16.5: players may change how often the game saves itself."""
    game.saves.assign_slot(1, "Test Game")
    game.saves.set_autosave_interval(1)
    assert game.saves.autosave_interval_minutes == 1

    game.saves.record_playtime(59)
    assert not game.saves.store.info(1).exists
    game.saves.record_playtime(2)
    assert game.saves.store.info(1).exists


def test_autosaving_can_be_turned_off(game):
    game.saves.assign_slot(1, "Test Game")
    game.saves.set_autosave_interval(0)

    game.saves.record_playtime(60 * 60)

    assert not game.saves.store.info(1).exists


# -- failure handling (V16.4) ---------------------------------------------


def test_a_failed_save_is_reported_rather_than_crashing(game, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("the disk is full")

    monkeypatch.setattr(game.saves.store, "write", explode)
    result = game.saves.save_to_slot(1)
    assert not result.ok
    assert "the disk is full" in result.message
    # The game is still running and still marked unsaved.
    assert game.running


def test_loading_a_missing_slot_is_reported(game):
    outcome = game.saves.load_from_slot(4)
    assert not outcome.ok
    assert "could not be opened" in outcome.describe()


def test_save_and_exit_leaves_only_when_the_save_succeeds(game):
    """V16.4 step 5: on success the player returns to the Main Menu.

    Leaving a session is not leaving the program, so the application keeps
    running — it is showing the menu rather than a world.
    """
    game._prompt_exit()
    game.popups.current.chosen = "exit"
    game.popups.handle_event(_dummy_event())

    assert game.in_menu is True
    assert game.running is True
    assert game.saves.store.info("1").exists


def test_save_and_exit_keeps_playing_when_saving_fails(game, monkeypatch):
    monkeypatch.setattr(game.saves.store, "write",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("no space")))
    game._prompt_exit()
    game.popups.current.chosen = "exit"
    game.popups.handle_event(_dummy_event())
    # V16.4 step 6: a failed save returns the player to the running game, so
    # another attempt can be made rather than the session being lost.
    assert game.running is True
    assert game.in_menu is False
    assert game.popups.is_open


def _dummy_event():
    import pygame

    return pygame.event.Event(pygame.USEREVENT)


# -- unsaved changes and playtime (V13.22, V14.19, V16.16) ----------------


def test_saving_clears_the_unsaved_marker(game):
    game.saves.mark_changed()
    assert game.saves.unsaved_changes
    game.saves.save_to_slot(1)
    assert not game.saves.unsaved_changes


def test_playtime_accumulates_and_is_saved(game):
    game.saves.record_playtime(12.5)
    game.saves.record_playtime(-5)  # ignored
    assert game.saves.playtime_seconds == 12.5
    game.saves.save_to_slot(1)
    assert game.saves.store.info(1).metadata.playtime_seconds == 12.5


def test_each_save_keeps_its_own_identity(game):
    game.saves.save_to_slot(1)
    first = game.saves.store.info(1).metadata.save_id
    game.saves.save_to_slot(2)
    # The same playthrough keeps one identity across its slots (V16.17).
    assert game.saves.store.info(2).metadata.save_id == first


def test_a_save_stays_small_after_long_play(game):
    game.context.engine.run_days(336 * 3)
    game.saves.save_to_slot(1)
    size = game.saves.store.path_for(1).stat().st_size
    # V16.20: files should stay efficient even after years of simulation.
    assert size < 2_000_000


def test_personal_holdings_and_unlocks_survive_a_save(game):
    """V16.11: the player's own position is gameplay state like any other."""
    portfolio = game.context.portfolio
    listing = game.context.market.active_listings()[0]
    portfolio.buy(listing.company_id, 8, game.context.engine.date.day)
    game.context.player.unlocks.unlock(CREATE_COMPANY)
    held = portfolio.value()

    game.saves.save_to_slot(1)
    game.saves.load_from_slot(1)

    restored = game.context.portfolio
    assert restored.shares_of(listing.company_id) == 8
    assert restored.value() == held
    assert game.context.unlocks.has(CREATE_COMPANY)


def test_a_reloaded_player_can_still_trade(game):
    """The portfolio must come back attached to the reloaded market."""
    listing = game.context.market.active_listings()[0]
    game.context.portfolio.buy(listing.company_id, 5, game.context.engine.date.day)
    game.saves.save_to_slot(1)
    game.saves.load_from_slot(1)

    ok, message = game.context.portfolio.sell(
        listing.company_id, 5, game.context.engine.date.day
    )
    assert ok, message
    assert game.context.portfolio.shares_of(listing.company_id) == 0


def test_a_temporary_file_is_not_shared_between_processes(store, monkeypatch):
    """Two games sharing a save directory must not collide mid-write.

    A fixed temporary name looks atomic but is not: the first process to finish
    moves the file out from under the second, which then fails with the old
    save already replaced.
    """
    import os as os_module

    seen = []
    real_replace = os_module.replace

    def record(source, destination):
        seen.append(str(source))
        return real_replace(source, destination)

    monkeypatch.setattr("apex_horizon.engine.save.slots.os.replace", record)
    store.write(1, sample_document())

    assert seen and str(os_module.getpid()) in seen[0]


def test_a_failed_write_leaves_no_stray_temporary(store, monkeypatch):
    def explode(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr("apex_horizon.engine.save.slots.os.replace", explode)
    with pytest.raises(OSError):
        store.write(1, sample_document())

    assert not list(store.directory.glob("*.tmp"))


def test_an_interrupted_write_leaves_the_previous_save_intact(store, monkeypatch):
    """V16.19: an interruption must never destroy the save already there."""
    store.write(1, sample_document())
    original = store.read(1)

    def explode(source, destination):
        raise OSError("interrupted")

    monkeypatch.setattr("apex_horizon.engine.save.slots.os.replace", explode)
    with pytest.raises(OSError):
        store.write(1, sample_document())

    assert store.read(1) == original


def test_unlock_effects_are_reapplied_after_loading(game):
    """V6.3, V16.28: a reloaded game must behave exactly as the saved one did."""
    from apex_horizon.engine.unlocks import BASIC_NEWS, MARKET_NEWS

    for key in (BASIC_NEWS, MARKET_NEWS):
        game.context.player.unlocks.unlock(key)
    game.effects.apply(game.context)
    tier = game.context.news.tier

    game.saves.save_to_slot(1)
    game.saves.load_from_slot(1)

    assert game.context.unlocks.has(MARKET_NEWS)
    # The tier is not merely stored — it is re-derived from the tree, so the
    # restored world is configured by what the player earned.
    assert game.context.news.enabled
    assert game.context.news.tier == tier
