"""Tests for the Unlock Tree (Design Bible Volume 6)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.company import Player
from apex_horizon.engine.unlocks import (
    BASIC_INVESTING,
    CREATE_COMPANY,
    UNLOCKS,
    UnlockTree,
)
from apex_horizon.engine.values import Calendar, Money, set_calendar


@pytest.fixture(autouse=True)
def _shared_calendar():
    set_calendar(Calendar(days_per_week=7, weeks_per_month=4, months_per_year=12))
    yield
    set_calendar(None)


# -- the start of the tree (V6.4) -----------------------------------------


def test_the_player_always_begins_with_basic_investing():
    """V6.4 states it outright, and the opening of the game depends on it."""
    tree = UnlockTree()
    assert tree.has(BASIC_INVESTING)
    assert not tree.has(CREATE_COMPANY)


def test_create_company_follows_basic_investing():
    """V6.5: the primary progression runs Basic Investing -> Create Company."""
    tree = UnlockTree()
    available = [unlock.key for unlock in tree.available()]
    assert available == [CREATE_COMPANY]


def test_progression_cannot_be_skipped():
    """V6.9: every unlock requires completion of its prerequisite."""
    tree = UnlockTree()
    tree.unlocked.clear()  # nothing owned at all

    allowed, reason = tree.can_purchase(CREATE_COMPANY, Money(1_000_000))
    assert not allowed
    assert "Basic Investing" in reason


# -- buying an unlock -----------------------------------------------------


def test_an_unlock_cannot_be_bought_without_the_money():
    tree = UnlockTree()
    cost = tree.cost_of(CREATE_COMPANY)

    allowed, reason = tree.can_purchase(CREATE_COMPANY, cost - Money(1))
    assert not allowed
    assert "costs" in reason


def test_an_unlock_can_be_bought_once_afforded():
    tree = UnlockTree()
    assert tree.can_purchase(CREATE_COMPANY, tree.cost_of(CREATE_COMPANY))[0]


def test_an_unlock_is_not_bought_twice():
    tree = UnlockTree()
    tree.unlock(CREATE_COMPANY)

    allowed, reason = tree.can_purchase(CREATE_COMPANY, Money(1_000_000))
    assert not allowed
    assert "already unlocked" in reason


def test_costs_come_from_configuration():
    """The project manager tunes prices without touching code (V15.10)."""
    tree = UnlockTree()
    assert tree.cost_of(CREATE_COMPANY) == Money(
        tree.config.get_int("unlocks.create_company_cost")
    )
    # An unlock the player starts with is never sold to them.
    assert tree.cost_of(BASIC_INVESTING) == Money.zero()


def test_no_unlock_hard_codes_its_price():
    for unlock in UNLOCKS:
        if unlock.owned_at_start:
            continue
        assert unlock.cost_key, f"{unlock.name} must read its price from config"


def test_unlocking_notifies_listeners():
    tree = UnlockTree()
    seen = []
    tree.on_unlocked.append(seen.append)

    tree.unlock(CREATE_COMPANY)

    assert [unlock.key for unlock in seen] == [CREATE_COMPANY]


# -- the gate on founding (V3.3, V6.2) ------------------------------------


def test_founding_requires_the_create_company_unlock():
    player = Player("Owner", cash=Money(1_000_000))

    allowed, reason = player.can_found_company()
    assert not allowed
    assert "Create Company" in reason

    player.unlocks.unlock(CREATE_COMPANY)
    assert player.can_found_company()[0]


def test_the_unlock_does_not_found_a_company_by_itself():
    """Unlocking is permission; founding is a separate, paid decision."""
    player = Player("Owner", cash=Money(1_000_000))
    player.unlocks.unlock(CREATE_COMPANY)

    assert player.company is None
    assert player.cash == Money(1_000_000), "the unlock does not charge founding"


def test_founding_still_costs_its_own_price_after_the_unlock():
    player = Player("Owner", cash=Money(40_000))
    player.unlocks.unlock(CREATE_COMPANY)

    player.found_company("Test Capital", day=1)

    assert player.cash == Money(40_000) - player.founding_cost


# -- persistence (V16.11) -------------------------------------------------


def test_unlocks_survive_a_round_trip():
    tree = UnlockTree()
    tree.unlock(CREATE_COMPANY)

    restored = UnlockTree()
    restored.restore(tree.state())

    assert restored.has(CREATE_COMPANY)
    assert restored.has(BASIC_INVESTING)


def test_a_save_without_unlocks_still_starts_with_basic_investing():
    """V16.15: a save written before the tree existed must still load."""
    restored = UnlockTree()
    restored.restore({})

    assert restored.has(BASIC_INVESTING)
    assert not restored.has(CREATE_COMPANY)
