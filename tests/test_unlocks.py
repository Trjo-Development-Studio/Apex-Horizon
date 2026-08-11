"""Tests for the Unlock Tree (Design Bible Volume 6)."""

from __future__ import annotations

from decimal import Decimal
from itertools import pairwise

import pytest

from apex_horizon.engine.company import Player
from apex_horizon.engine.unlocks import (
    BASIC_ANALYTICS,
    BASIC_INVESTING,
    BASIC_NEWS,
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


def test_the_two_basic_investing_branches_open_immediately():
    """V6.5 and V6.6: Create Company, plus the Analytics and News branch roots."""
    tree = UnlockTree()
    available = [unlock.key for unlock in tree.available()]
    assert set(available) == {CREATE_COMPANY, BASIC_ANALYTICS, BASIC_NEWS}


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
    multipliers = tree.config.get_list("unlocks.cost_multipliers")
    founding = tree.config.get_int("company.founding_cost")
    unlock = tree.by_key[CREATE_COMPANY]

    assert tree.cost_of(CREATE_COMPANY) == Money(
        Decimal(founding) * Decimal(str(multipliers[unlock.cost_tier]))
    )
    # An unlock the player starts with is never sold to them.
    assert tree.cost_of(BASIC_INVESTING) == Money.zero()


def test_prices_rise_with_depth():
    """V6.11: unlocks should appear gradually as the company grows."""
    tree = UnlockTree()
    costs = [
        tree.cost_of(unlock.key) for unlock in tree.branch("news")
    ]
    assert costs == sorted(costs)
    assert costs[0] < costs[-1]


def test_the_create_company_price_follows_the_founding_cost():
    """PM decision: the two stay in proportion when either is retuned."""
    tree = UnlockTree()
    before = tree.cost_of(CREATE_COMPANY)

    original = tree.config.get_int("company.founding_cost")
    tree.config._data["company"]["founding_cost"] = original * 2
    try:
        assert tree.cost_of(CREATE_COMPANY) == before + before
    finally:
        tree.config._data["company"]["founding_cost"] = original


def test_no_unlock_hard_codes_its_price():
    """Every price is a multiple from configuration, never a literal (V15.10)."""
    tree = UnlockTree()
    multipliers = tree.config.get_list("unlocks.cost_multipliers")
    for unlock in UNLOCKS:
        if unlock.owned_at_start:
            continue
        assert 0 <= unlock.cost_tier < len(multipliers), unlock.name
        assert tree.cost_of(unlock.key).is_positive, unlock.name


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


# -- the shape of the tree (V6.5-V6.8) ------------------------------------


def test_the_tree_is_acyclic_and_fully_connected():
    """V6.19: a directed acyclic graph, every node reachable from the root."""
    tree = UnlockTree()
    reachable = {BASIC_INVESTING}
    changed = True
    while changed:
        changed = False
        for unlock in tree.all:
            if unlock.key in reachable:
                continue
            if unlock.requires and all(r in reachable for r in unlock.requires):
                reachable.add(unlock.key)
                changed = True

    assert reachable == {unlock.key for unlock in tree.all}, (
        "every unlock must trace back to Basic Investing (V6.10)"
    )


def test_no_unlock_requires_itself_or_something_later():
    """A cycle would make part of the tree unreachable (V6.19)."""
    tree = UnlockTree()
    order = {unlock.key: index for index, unlock in enumerate(tree.all)}
    for unlock in tree.all:
        assert unlock.key not in unlock.requires
        for requirement in unlock.requires:
            assert requirement in order, f"{unlock.name} requires an unknown unlock"


def test_investment_funds_needs_every_branch():
    """V6.8 lists seven prerequisites, one from the end of each branch."""
    from apex_horizon.engine.unlocks import (
        BETTER_ANALYTICS_3,
        BETTER_EMPLOYEES_3,
        BETTER_FINANCE_3,
        BETTER_TRAINING_3,
        BREAKING_NEWS,
        COMPANY_ANALYTICS,
        EMPLOYEE_PERFORMANCE,
        INVESTMENT_FUNDS,
    )

    tree = UnlockTree()
    assert set(tree.by_key[INVESTMENT_FUNDS].requires) == {
        BETTER_ANALYTICS_3, BETTER_FINANCE_3, BETTER_EMPLOYEES_3, COMPANY_ANALYTICS,
        BETTER_TRAINING_3, EMPLOYEE_PERFORMANCE, BREAKING_NEWS,
    }


def test_an_unbuilt_system_cannot_be_bought():
    """V6.3: never sell an unlock that changes nothing.

    Every unlock in the shipped tree is now built, so the guard is exercised
    against a node marked unbuilt rather than against whichever one happens to
    be waiting for its system.
    """
    from apex_horizon.engine.unlocks import Unlock

    tree = UnlockTree()
    pending = Unlock(key="not_built_yet", name="Not Built Yet",
                     description="A system that does not exist.",
                     requires=(BASIC_INVESTING,), cost_tier=0, implemented=False)
    tree.all = (*tree.all, pending)
    tree.by_key[pending.key] = pending

    allowed, reason = tree.can_purchase(pending.key, Money(100_000_000))
    assert not allowed
    assert "later version" in reason
    assert pending.key not in {unlock.key for unlock in tree.available()}


def test_every_unlock_in_the_tree_is_now_built():
    """The tree no longer advertises anything it cannot deliver (V6.3)."""
    tree = UnlockTree()
    assert [unlock.name for unlock in tree.all if not unlock.implemented] == []


def test_every_branch_is_a_straight_sequence():
    """V6.9: progression is linear along a branch, left to right."""
    tree = UnlockTree()
    for name in ("analytics", "news", "finance", "employees", "training", "recruitment"):
        branch = tree.branch(name)
        assert branch, name
        for earlier, later in pairwise(branch):
            assert earlier.key in later.requires, (
                f"{later.name} should follow {earlier.name}"
            )


# -- what unlocks actually do (V6.3) --------------------------------------


class FakeRoster:
    def __init__(self):
        self.recruitment_tier = 0
        self.training_allowed = False
        self.training_speed = 1.0
        self.applicant_pool = 0
        self.reputation_weight = 0.0
        self.strengths_visible = False
        self.performance_visible = False


class FakeFunds:
    def __init__(self):
        self.unlocked = False


class FakeSubsidiaries:
    def __init__(self):
        self.unlocked = False


class FakeCompany:
    def __init__(self):
        self.level = 1
        self.borrowing_allowed = False
        self.finance_tier = 0
        self.employees = FakeRoster()
        self.funds = FakeFunds()
        self.subsidiaries = FakeSubsidiaries()
        self.max_level = 5

    def set_level(self, level):
        self.level = level


class FakeNews:
    def __init__(self):
        self.enabled = True
        self.tier = None


class FakeAnalytics:
    def __init__(self):
        self.enabled = True
        self.tier = None
        self.company_analytics = False


class FakeContext:
    def __init__(self):
        self.news = FakeNews()
        self.analytics = FakeAnalytics()
        self.company = FakeCompany()

    def snapshot(self) -> tuple:
        """Everything the effects layer is allowed to configure."""
        company = self.company
        return (
            vars(self.news).copy(),
            vars(self.analytics).copy(),
            company.level, company.borrowing_allowed, company.finance_tier,
            company.funds.unlocked,
            company.subsidiaries.unlocked,
            vars(company.employees).copy(),
        )


def applied(*keys):
    """A context with the given unlocks granted and their effects applied."""
    from apex_horizon.engine.unlocks import UnlockEffects

    tree = UnlockTree()
    for key in keys:
        tree.unlock(key)
    context = FakeContext()
    UnlockEffects(tree).apply(context)
    return context


def test_company_level_follows_the_company_branch():
    from apex_horizon.engine.unlocks import (
        COMPANY_LEVEL_2,
        COMPANY_LEVEL_3,
        COMPANY_LEVEL_4,
        COMPANY_LEVEL_5,
    )

    assert applied().company.level == 1
    assert applied(COMPANY_LEVEL_2).company.level == 2
    levels = (COMPANY_LEVEL_2, COMPANY_LEVEL_3, COMPANY_LEVEL_4, COMPANY_LEVEL_5)
    assert applied(*levels).company.level == 5


def test_skill_ceilings_follow_the_employee_branch():
    """V6.7.2 gives 1-20, 1-30 and 1-40 for the three levels."""
    from apex_horizon.engine.unlocks import (
        BETTER_EMPLOYEES_1,
        BETTER_EMPLOYEES_2,
        BETTER_EMPLOYEES_3,
    )

    assert applied().company.employees.recruitment_tier == 0
    assert applied(BETTER_EMPLOYEES_1).company.employees.recruitment_tier == 1
    assert applied(
        BETTER_EMPLOYEES_1, BETTER_EMPLOYEES_2, BETTER_EMPLOYEES_3
    ).company.employees.recruitment_tier == 3


def test_training_is_gated_and_then_improves():
    from apex_horizon.engine.unlocks import BETTER_TRAINING_1, EMPLOYEE_TRAINING

    assert not applied().company.employees.training_allowed
    granted = applied(EMPLOYEE_TRAINING).company.employees
    assert granted.training_allowed
    assert granted.training_speed == 1.0

    faster = applied(EMPLOYEE_TRAINING, BETTER_TRAINING_1).company.employees
    assert faster.training_speed > granted.training_speed


def test_borrowing_is_gated_by_the_finance_branch():
    from apex_horizon.engine.unlocks import BETTER_FINANCE_1, FINANCE

    assert not applied().company.borrowing_allowed
    assert applied(FINANCE).company.borrowing_allowed
    assert applied(FINANCE, BETTER_FINANCE_1).company.finance_tier == 1


def test_the_recruitment_branch_reveals_and_widens():
    from apex_horizon.engine.unlocks import (
        BETTER_RECRUITMENT,
        EMPLOYEE_PERFORMANCE,
        EMPLOYEE_STRENGTHS,
        MORE_APPLICANTS,
    )

    plain = applied().company.employees
    assert not plain.strengths_visible and not plain.performance_visible

    wider = applied(BETTER_RECRUITMENT, MORE_APPLICANTS).company.employees
    assert wider.applicant_pool > plain.applicant_pool
    assert wider.reputation_weight > plain.reputation_weight

    seen = applied(
        BETTER_RECRUITMENT, MORE_APPLICANTS, EMPLOYEE_STRENGTHS, EMPLOYEE_PERFORMANCE
    ).company.employees
    assert seen.strengths_visible and seen.performance_visible


def test_every_purchasable_unlock_changes_something():
    """V6.3: the player should never buy something insignificant.

    Each unlock is applied on top of its prerequisites and the resulting
    configuration compared against the same tree without it.

    One is exempt, for a stated reason rather than by oversight: Create Company
    acts on the founding gate in ``Player`` rather than on any system this layer
    configures. (The structural Employees root was the other exemption until it
    was removed from the catalogue entirely, 2026-08-11.)
    """
    from apex_horizon.engine.unlocks import UnlockEffects

    structural = {CREATE_COMPANY}
    reference = UnlockTree()
    for unlock in reference.all:
        if unlock.owned_at_start or not unlock.implemented or unlock.key in structural:
            continue

        before, after = UnlockTree(), UnlockTree()
        for key in unlock.requires:
            before.unlock(key)
            after.unlock(key)
        after.unlock(unlock.key)

        first, second = FakeContext(), FakeContext()
        UnlockEffects(before).apply(first)
        UnlockEffects(after).apply(second)
        assert first.snapshot() != second.snapshot(), (
            f"{unlock.name} changes nothing when unlocked"
        )


# -- the 2026-08-11 employee/company rewiring -----------------------------


def test_the_structural_employees_unlock_is_gone():
    """Project manager, 2026-08-11: it did nothing but gate the levels under
    it, so the levels hang off Create Company directly instead."""
    tree = UnlockTree()
    assert "employees" not in tree.by_key
    assert not any(u.name == "Employees" for u in tree.all)
    # and nothing is left requiring it
    for unlock in tree.all:
        assert "employees" not in unlock.requires, unlock.name


def test_the_employee_branch_runs_from_create_company_to_automated_recruitment():
    from apex_horizon.engine.unlocks import (
        AUTOMATED_RECRUITMENT,
        BETTER_EMPLOYEES_1,
        BETTER_EMPLOYEES_2,
        BETTER_EMPLOYEES_3,
    )

    tree = UnlockTree()
    assert tree.by_key[BETTER_EMPLOYEES_1].requires == (CREATE_COMPANY,)
    assert tree.by_key[BETTER_EMPLOYEES_2].requires == (BETTER_EMPLOYEES_1,)
    assert tree.by_key[BETTER_EMPLOYEES_3].requires == (BETTER_EMPLOYEES_2,)
    assert tree.by_key[AUTOMATED_RECRUITMENT].requires == (BETTER_EMPLOYEES_3,)
    assert [u.key for u in tree.branch("employees")] == [
        BETTER_EMPLOYEES_1, BETTER_EMPLOYEES_2, BETTER_EMPLOYEES_3, AUTOMATED_RECRUITMENT,
    ]


def test_the_company_branches_start_at_create_company():
    """Finance, Training and Recruitment come off Create Company, not
    Company Level 2 (project manager, 2026-08-11)."""
    from apex_horizon.engine.unlocks import BETTER_RECRUITMENT, EMPLOYEE_TRAINING, FINANCE

    tree = UnlockTree()
    for key in (FINANCE, EMPLOYEE_TRAINING, BETTER_RECRUITMENT):
        assert tree.by_key[key].requires == (CREATE_COMPANY,), key
    # The spine itself is unchanged: the Company Levels still follow each other.
    assert tree.by_key["company_level_3"].requires == ("company_level_2",)


def test_the_catalogue_size_is_whatever_the_catalogue_says():
    """The count is data-driven: this asserts today's number so a change is
    noticed, and derives it from the catalogue so nothing hardcodes a cap."""
    from apex_horizon.engine.unlocks.catalogue import UNLOCKS

    tree = UnlockTree()
    assert len(tree.all) == len(UNLOCKS) == 33
    assert len({u.key for u in tree.all}) == len(tree.all), "keys must be unique"


def test_an_unlock_removed_from_the_catalogue_is_dropped_from_an_old_save():
    """A save written when "Employees" existed must not go on counting it
    towards "N of M unlocked" (V16.15)."""
    tree = UnlockTree()
    tree.restore({"unlocked": ["basic_investing", "create_company", "employees"]})
    assert "employees" not in tree.unlocked
    assert tree.unlocked <= set(tree.by_key)
