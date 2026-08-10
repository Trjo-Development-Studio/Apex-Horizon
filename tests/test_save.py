"""Tests for the Save System (Design Bible Volume 16)."""

from __future__ import annotations

import json

import pytest

from apex_horizon.engine.save import (
    SAVE_FORMAT_VERSION,
    SaveDocument,
    SaveFormatError,
    SaveMetadata,
    SaveStore,
    SaveSummary,
    decode,
    encode,
    read_save,
    repair,
    validate,
)
from apex_horizon.engine.save import validation as validation_module
from apex_horizon.engine.save.format import MAGIC
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.ui.app import GameApp


@pytest.fixture(autouse=True)
def _calendar():
    set_calendar(Calendar(7, 4, 12))
    yield
    set_calendar(None)


@pytest.fixture
def store(tmp_path):
    return SaveStore(tmp_path, manual_slots=5)


@pytest.fixture
def game(tmp_path):
    app = GameApp(size=(1100, 700), seed=2026)
    app.saves.store = SaveStore(tmp_path, manual_slots=5)
    yield app
    app.shutdown()


def sample_document() -> SaveDocument:
    return SaveDocument(
        metadata=SaveMetadata(name="Meridian Capital"),
        summary=SaveSummary(money="1000", net_worth="2500", year=3, month=8, week=2, day=4),
        state={"engine": {}, "world": {}, "market": {}, "economy": {}, "player": {}},
    )


# -- the file format (V16.18 - V16.20) ------------------------------------


def test_a_save_round_trips():
    document = sample_document()
    restored = decode(encode(document))
    assert restored.metadata.name == "Meridian Capital"
    assert restored.summary.year == 3
    assert restored.state == document.state


def test_saves_are_compressed_and_not_plain_text():
    # V16.18: compression keeps files small and discourages casual editing.
    document = sample_document()
    document.state["market"] = {f"listing-{i}": {"price": "123.45"} for i in range(400)}
    raw = encode(document)
    plain = json.dumps(document.to_dict()).encode()
    assert len(raw) < len(plain) / 2
    assert b"listing-1" not in raw


def test_a_save_is_recognisable_and_versioned():
    raw = encode(sample_document())
    assert raw.startswith(MAGIC)
    assert decode(raw).metadata.save_format_version == SAVE_FORMAT_VERSION


def test_corruption_is_detected(tmp_path):
    # V16.13: an invalid save must never silently load.
    raw = bytearray(encode(sample_document()))
    raw[-5] ^= 0xFF
    with pytest.raises(SaveFormatError, match="damaged"):
        decode(bytes(raw))


def test_a_truncated_file_is_rejected():
    raw = encode(sample_document())[:20]
    with pytest.raises(SaveFormatError):
        decode(raw)


def test_a_foreign_file_is_rejected():
    with pytest.raises(SaveFormatError, match="not an Apex Horizon save"):
        decode(b"just some other file entirely")


def test_a_newer_container_is_refused():
    raw = bytearray(encode(sample_document()))
    raw[len(MAGIC)] = 99
    with pytest.raises(SaveFormatError, match="newer version"):
        decode(bytes(raw))


def test_metadata_carries_what_volume_16_16_requires():
    metadata = decode(encode(sample_document())).metadata
    assert metadata.save_id
    assert metadata.game_version
    assert metadata.created and metadata.last_saved
    assert isinstance(metadata.save_format_version, int)


# -- validation, repair and migration (V16.13 - V16.15) -------------------


def test_a_complete_save_validates():
    assert validate(sample_document()).valid


def test_missing_systems_are_reported():
    document = sample_document()
    del document.state["market"]
    result = validate(document)
    assert not result.valid
    assert "market" in result.describe()


def test_wrong_types_are_reported():
    document = sample_document()
    document.state["economy"] = "not a mapping"
    assert not validate(document).valid


def test_a_save_from_a_newer_game_is_refused():
    document = sample_document()
    document.metadata.save_format_version = SAVE_FORMAT_VERSION + 5
    assert "newer version" in validate(document).describe()


def test_repair_fills_in_what_it_safely_can():
    document = sample_document()
    document.metadata.save_id = ""
    document.state["market"] = 42
    repaired, notes = repair(document)
    assert repaired.metadata.save_id
    assert notes
    assert "market" not in repaired.state


def test_migration_upgrades_an_older_save(monkeypatch):
    # V16.15: older saves are migrated automatically.
    monkeypatch.setitem(validation_module.MIGRATIONS, 0,
                        lambda doc: _add_marker(doc))
    document = sample_document()
    document.metadata.save_format_version = 0
    outcome = read_save(encode(document))
    assert outcome.ok
    assert outcome.document is not None
    assert outcome.document.state["migrated"] is True
    assert outcome.document.metadata.save_format_version == SAVE_FORMAT_VERSION


def _add_marker(document: SaveDocument) -> SaveDocument:
    document.state["migrated"] = True
    return document


def test_an_unmigratable_save_is_reported_rather_than_loaded():
    document = sample_document()
    document.metadata.save_format_version = 0  # no migration registered
    outcome = read_save(encode(document))
    assert not outcome.ok
    assert "cannot be upgraded" in outcome.describe()


def _with_broken_checksum() -> bytes:
    """A save whose integrity check fails but whose contents are still intact."""
    raw = bytearray(encode(sample_document()))
    raw[len(MAGIC) + 1] ^= 0xFF
    return bytes(raw)


def test_a_damaged_save_asks_before_loading():
    # V16.14: if repair does not succeed the player is asked, not refused.
    outcome = read_save(_with_broken_checksum())
    assert not outcome.ok
    assert outcome.needs_confirmation
    assert outcome.document is not None  # contents were salvaged


def test_a_damaged_save_can_be_loaded_on_request():
    outcome = read_save(_with_broken_checksum(), allow_damaged=True)
    assert outcome.ok
    assert "damaged" in outcome.describe()
    assert outcome.document is not None
    assert outcome.document.metadata.name == "Meridian Capital"


def test_a_save_whose_contents_are_destroyed_cannot_be_salvaged():
    # Corrupting the compressed body itself is beyond repair, and is reported
    # rather than guessed at.
    raw = bytearray(encode(sample_document()))
    raw[-5] ^= 0xFF
    outcome = read_save(bytes(raw))
    assert not outcome.ok
    assert outcome.document is None
    assert "damaged" in outcome.describe()


def test_unreadable_bytes_cannot_be_salvaged():
    outcome = read_save(MAGIC + b"\x01" + b"\x00" * 4 + b"garbage")
    assert not outcome.ok
    assert outcome.document is None


# -- slots (V16.7 - V16.9, V16.21, V16.22) --------------------------------


def test_there_are_five_slots_and_no_separate_autosave(store):
    """PM decision: autosaving writes to the game's own slot, not a sixth one."""
    names = store.slot_names()
    assert names == ["1", "2", "3", "4", "5"]
    assert len(store.list_slots()) == 5


def test_an_empty_slot_describes_itself(store):
    info = store.info(1)
    assert not info.exists
    assert info.describe() == "Empty"
    assert info.label == "Slot 1"


def test_a_written_slot_shows_its_details(store):
    store.write(1, sample_document())
    info = store.info(1)
    assert info.exists
    assert "Meridian Capital" in info.describe()
    assert "Year 3" in info.describe()
    assert info.summary.net_worth_value == Money(2500)


def test_a_slot_description_includes_money_and_playtime(store):
    """QoL pass, 2026-08-10: Save Name, Money, Net Worth, Y/M/W/D and
    Playtime, all in one description — every figure was already computed on
    SaveSummary/SaveMetadata, this only formats what is already there."""
    document = sample_document()
    document.metadata.playtime_seconds = 3 * 3600 + 22 * 60
    store.write(1, document)
    description = store.info(1).describe()
    assert "$1,000" in description  # money, distinct from net worth
    assert "$2,500" in description  # net worth
    assert "3h 22m played" in description


def test_playtime_formats_by_its_own_magnitude():
    from apex_horizon.engine.save.slots import _format_playtime

    assert _format_playtime(0) == "0m played"
    assert _format_playtime(45 * 60) == "45m played"
    assert _format_playtime(3 * 3600 + 22 * 60) == "3h 22m played"
    assert _format_playtime(2 * 86400 + 5 * 3600) == "2d 5h played"


def test_writing_is_atomic_and_leaves_no_temporary_files(store):
    store.write(2, sample_document())
    assert not list(store.directory.glob("*.tmp"))


def test_a_failed_write_leaves_the_previous_save_intact(store, monkeypatch):
    store.write(1, sample_document())
    original = store.read(1)

    def explode(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", explode)
    with pytest.raises(OSError):
        store.write(1, sample_document())
    # The old save is still readable.
    assert store.read(1) == original


def test_a_damaged_slot_is_shown_rather_than_hidden(store):
    path = store.path_for(3)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"not a save at all")
    info = store.info(3)
    assert info.exists and info.damaged
    assert info.describe() == "Damaged save"


def test_slots_can_be_deleted(store):
    store.write(1, sample_document())
    assert store.delete(1) is True
    assert store.delete(1) is False


def test_export_and_import(store, tmp_path):
    store.write(1, sample_document())
    exported = store.export(1, tmp_path / "backup" / "my-save.ahsave")
    assert exported.exists()

    store.import_file(exported, 4)
    assert store.info(4).exists
    assert store.info(4).metadata.name == "Meridian Capital"


def test_importing_a_bad_file_is_refused_before_overwriting(store, tmp_path):
    store.write(2, sample_document())
    original = store.read(2)
    bad = tmp_path / "bad.ahsave"
    bad.write_bytes(b"nonsense")
    with pytest.raises(SaveFormatError):
        store.import_file(bad, 2)
    assert store.read(2) == original


# -- saving and loading a real game (V16.11) ------------------------------


def test_a_real_game_round_trips(game):
    game.context.engine.run_days(120)
    game.context.player.cash = Money(90_000)
    game.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = game.context.player.found_company("Meridian Capital", 1)
    company.register(game.context.engine)
    game.context.engine.run_days(60)

    day = game.context.engine.date.day
    prices = {i.company_id: i.price for i in game.context.market.active_listings()}
    health = game.context.economy.health
    companies = len(game.context.world.companies)

    assert game.saves.save_to_slot(1, "Round trip").ok
    game.context.engine.run_days(200)  # move on, then go back
    assert game.saves.load_from_slot(1).ok

    assert game.context.engine.date.day == day
    assert game.context.economy.health == health
    assert len(game.context.world.companies) == companies
    assert game.context.company.name == "Meridian Capital"
    for company_id, price in prices.items():
        assert game.context.market.listing_for(company_id).price == price


def test_a_hired_employee_survives_save_and_load(game):
    """Bug fix, 2026-08-09, Test 4: a hire is real state, not a UI-only change.

    Goes through the same dispatcher the Hire button drives, rather than
    calling ``roster.hire`` directly, so the test covers the path a player's
    click actually takes and not just the engine method underneath it.
    """
    game.context.player.cash = Money(60_000)
    game.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = game.context.player.found_company("Meridian Capital", 1)
    company.register(game.context.engine)
    roster = company.employees
    roster.refresh_applicants(game.context.engine.rng, game.context.names,
                              game.context.allocator, game.context.engine.date.day)
    applicant = roster.applicants[0]

    page = game.pages["company:employees"]
    page.requested_hire = applicant.id
    game._handle_employees_page(page)
    assert any(e.id == applicant.id for e in roster.employees), "the hire itself must succeed"

    assert game.saves.save_to_slot(1, "Hiring round trip").ok
    game.context.engine.run_days(30)  # move on, then load back over it
    assert game.saves.load_from_slot(1).ok

    reloaded = game.context.company.employees
    assert any(e.id == applicant.id for e in reloaded.employees), \
        "the hired employee must still be on the roster after a reload"
    assert reloaded.is_full is False
    assert not any(a.id == applicant.id for a in reloaded.applicants), \
        "and must not have reappeared as an applicant"


def test_a_reloaded_game_continues_identically(game):
    game.context.engine.run_days(100)
    game.saves.save_to_slot(1)
    game.context.engine.run_days(30)
    expected = {i.company_id: i.price for i in game.context.market.active_listings()}

    game.saves.load_from_slot(1)
    game.context.engine.run_days(30)
    actual = {i.company_id: i.price for i in game.context.market.active_listings()}
    # Determinism survives the round trip (V15.11, V16.28).
    assert actual == expected


def test_a_company_founded_after_loading_matches_an_uninterrupted_game(game):
    """The world generator's own random stream is part of the save (V15.11).

    The market keeps listing new companies long after the world is built. If the
    generator restarted from the seed on every load, a company founded after
    loading would differ from the one an uninterrupted game would have founded —
    so saving and reloading would quietly change the future.
    """
    game.context.engine.run_days(100)
    game.saves.save_to_slot(1)
    at_save = len(game.context.world.companies)

    game.context.engine.run_days(120)
    expected = {c.id: c.name for c in game.context.world.companies}
    assert len(expected) > at_save, "the market should list new companies over 120 days"

    game.saves.load_from_slot(1)
    game.context.engine.run_days(120)
    actual = {c.id: c.name for c in game.context.world.companies}

    assert actual == expected


def test_price_history_survives_saving(game):
    # V4.22: market state including price history is saved in its entirety.
    game.context.engine.run_days(90)
    listing = game.context.market.active_listings()[0]
    history = list(listing.history)
    game.saves.save_to_slot(1)
    game.saves.load_from_slot(1)
    assert list(game.context.market.listing_for(listing.company_id).history) == history


def test_generation_state_survives_so_new_companies_stay_unique(game):
    game.context.engine.run_days(60)
    existing = {c.name for c in game.context.world.companies}
    game.saves.save_to_slot(1)
    game.saves.load_from_slot(1)
    game.context.engine.run_days(336 * 3)
    names = [c.name for c in game.context.world.companies]
    assert len(names) == len(set(names))
    assert existing <= set(names)


def test_the_summary_matches_the_game(game):
    game.context.player.cash = Money(12_345)
    document = game.saves.gather()
    assert document.summary.money_value == Money(12_345)
    assert document.summary.year == game.context.engine.date.year()


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
