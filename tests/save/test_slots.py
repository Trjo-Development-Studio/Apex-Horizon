"""Save slots, and saving and loading a real game."""

from __future__ import annotations

import pytest
from save_support import sample_document

from apex_horizon.engine.save import (
    SaveFormatError,
)
from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money

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


def test_an_empty_slot_is_titled_by_its_number(store):
    """Project manager correction, 2026-08-10: "Slot N" is the fallback for a
    slot with no game in it to name, not what every slot is called."""
    assert store.info(1).title == "Slot 1"


def test_a_written_slot_is_titled_by_the_saves_own_name(store):
    store.write(1, sample_document())
    info = store.info(1)
    assert info.title == "Meridian Capital"
    # The name belongs to the title, so the details beside it must not repeat
    # it — every list shows the two together.
    assert "Meridian Capital" not in info.describe()


def test_a_written_slot_shows_its_details(store):
    store.write(1, sample_document())
    info = store.info(1)
    assert info.exists
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


def test_the_date_label_matches_simulation_dates_own_format():
    """Formatting-consistency pass, 2026-08-10: SaveSummary.date_label() used
    to reimplement SimulationDate.label()'s exact format string independently
    rather than sharing it — a save slot's date must read exactly like the
    in-game date does everywhere else."""
    from apex_horizon.engine.save.format import SaveSummary
    from apex_horizon.engine.values import SimulationDate

    live_date = SimulationDate(200)
    summary = SaveSummary(
        year=live_date.year(), month=live_date.month(),
        week=live_date.week_of_month(), day=live_date.day_of_week(),
    )

    assert summary.date_label() == live_date.label()


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
