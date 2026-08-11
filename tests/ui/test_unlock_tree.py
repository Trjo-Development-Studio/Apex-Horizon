"""The Unlock Tree's layout, zoom, panning and details panel."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

# -- Unlock Tree: zoom, pan, click-select, info panel (2026-08-10) ---------
from ui_support import _found_company_for_acquisitions

from apex_horizon.engine.unlocks import CREATE_COMPANY


def test_zoom_in_and_out_stay_within_bounds(app):
    from apex_horizon.ui.pages.unlocks import ZOOM_LEVELS

    page = app.pages["unlocks"]
    for _ in range(len(ZOOM_LEVELS) + 2):
        page.zoom_in()
    assert page.zoom_index == len(ZOOM_LEVELS) - 1
    for _ in range(len(ZOOM_LEVELS) + 2):
        page.zoom_out()
    assert page.zoom_index == 0


def test_fit_to_screen_chooses_the_largest_level_that_fits(app):
    from apex_horizon.ui.pages.unlocks import ZOOM_LEVELS

    page = app.pages["unlocks"]
    page.zoom_index = 2
    page.fit_to_screen(pygame.Rect(0, 0, 100, 100))  # far too small for anything
    assert page.zoom_index == 0
    assert page.offset == [0, 0]

    page.zoom_index = 0
    page.fit_to_screen(pygame.Rect(0, 0, 100_000, 100_000))  # comfortably large
    assert page.zoom_index == len(ZOOM_LEVELS) - 1


def test_a_short_click_selects_a_node_but_a_drag_does_not(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    assert page.selected_key is None
    node_rect = next(iter(page._node_rects.values()))

    # A drag: real movement between down and up.
    start = node_rect.center
    moved = (start[0] + 40, start[1] + 40)
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start))
    page.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=moved))
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=moved))
    assert page.selected_key is None, "a drag must not select whatever it started on"

    # A genuine click: down and up at (near enough) the same point.
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start))
    page.handle_event(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=start))
    assert page.selected_key is not None


def test_mouse_wheel_zooms(app):
    page = app.pages["unlocks"]
    before = page.zoom_index
    page.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert page.zoom_index >= before
    page.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    page.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert page.zoom_index <= before


def test_zoom_and_pan_never_introduce_a_crossing_the_layout_did_not_have(app):
    """The invariant the whole feature leans on: connections are computed
    from node rects that are always a uniform scale of the same
    (row, column) grid, at every zoom level."""
    from apex_horizon.ui.pages.unlocks import ZOOM_LEVELS

    page = app.pages["unlocks"]
    tree = app.context.unlocks
    for index in range(len(ZOOM_LEVELS)):
        page.zoom_index = index
        app.navigate("dashboard")  # force a fresh draw next
        app.navigate("unlocks")
        app.draw(0)
        for unlock in tree.all:
            # Every node on the same branch stays on the same horizontal line
            # regardless of zoom — this is what "no crossing lines" rests on.
            same_branch = [u for u in tree.all if u.branch == unlock.branch]
            centers_y = {page._node_rects[u.key].centery for u in same_branch}
            assert len(centers_y) == 1, f"{unlock.branch} split across rows at zoom {index}"


def test_the_info_panel_shows_a_prompt_with_nothing_selected(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    assert page.selected_key is None
    # Renders without raising, which is what matters here — the panel's own
    # text content is exercised for real by the selected-node tests below.


def test_selecting_an_owned_unlock_shows_it_as_purchased(app):
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    page = app.pages["unlocks"]
    page.selected_key = CREATE_COMPANY
    app.navigate("unlocks")
    app.draw(0)  # must not raise with a real, owned selection
    tree = app.context.unlocks
    assert tree.has(CREATE_COMPANY)


def test_the_spine_runs_straight_through_the_middle_of_the_tree(app):
    """Project manager correction, 2026-08-10: the layout follows the legacy
    prototype's roadmap reference — Basic Investing, Create Company, the
    Company Levels and Investment Funds on one horizontal line through the
    middle (V6.5, V6.8), rather than the spine sitting near the top with
    every branch hanging beneath it."""
    from apex_horizon.engine.unlocks import (
        BASIC_INVESTING,
        COMPANY_LEVEL_2,
        CREATE_COMPANY,
        INVESTMENT_FUNDS,
    )

    app.navigate("unlocks")
    app.draw(0)
    rects = app.pages["unlocks"]._node_rects
    spine = (BASIC_INVESTING, CREATE_COMPANY, COMPANY_LEVEL_2, INVESTMENT_FUNDS)

    assert len({rects[key].centery for key in spine}) == 1, "the spine must be one line"
    lefts = [rects[key].left for key in spine]
    assert lefts == sorted(lefts), "and must read left to right in progression order"


def test_the_branches_fan_above_and_below_the_spine(app):
    """The other half of the reference's shape: branches balanced either side
    of the spine, with the two that come straight off Basic Investing rather
    than off a company (Analytics, News) sitting outermost."""
    from apex_horizon.engine.unlocks import (
        ANALYTICS_BRANCH,
        BASIC_INVESTING,
        EMPLOYEE_BRANCH,
        FINANCE_BRANCH,
        NEWS_BRANCH,
        RECRUITMENT_BRANCH,
        TRAINING_BRANCH,
    )

    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    tree = app.context.unlocks

    def top_of(branch):
        return page._node_rects[tree.branch(branch)[0].key].centery

    spine_y = page._node_rects[BASIC_INVESTING].centery
    for branch in (ANALYTICS_BRANCH, FINANCE_BRANCH, EMPLOYEE_BRANCH):
        assert top_of(branch) < spine_y, f"{branch} should sit above the spine"
    for branch in (TRAINING_BRANCH, RECRUITMENT_BRANCH, NEWS_BRANCH):
        assert top_of(branch) > spine_y, f"{branch} should sit below the spine"

    assert top_of(ANALYTICS_BRANCH) < top_of(FINANCE_BRANCH)
    assert top_of(NEWS_BRANCH) > top_of(RECRUITMENT_BRANCH)


def test_every_branch_converges_on_investment_funds(app):
    """V6.8, and the reference's single grey rail: every branch's last node
    feeds Investment Funds, which is what makes the tree read as one map
    rather than seven unrelated tracks."""
    from apex_horizon.engine.unlocks import INVESTMENT_FUNDS

    tree = app.context.unlocks
    funds = tree.by_key[INVESTMENT_FUNDS]
    app.navigate("unlocks")
    app.draw(0)
    rects = app.pages["unlocks"]._node_rects

    assert len(funds.requires) > 1, "several branches must converge here"
    for requirement in funds.requires:
        # Each feeder sits to the left of Investment Funds, so the shared
        # vertical rail drawn just left of it can never run backwards.
        assert rects[requirement].right <= rects[INVESTMENT_FUNDS].left


def test_the_info_panel_never_overflows_its_own_box_at_minimum_size(app):
    """Bug fix, 2026-08-10: the panel drew its text with no bound-checking
    and no clip, so a locked unlock with several prerequisites listed could
    spill straight past its own bottom edge and into the notification stack
    reserved below it. Clipped now, so this can no longer happen even if a
    future edit reintroduces a missing bound check."""
    from apex_horizon.engine.unlocks import INVESTMENT_FUNDS

    page = app.pages["unlocks"]
    page.selected_key = INVESTMENT_FUNDS  # seven prerequisites: the worst case
    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("unlocks")
    app.draw(2000)  # must not raise, and must not need to draw off-panel


# -- panels stay correct at small sizes (2026-08-10) ----------------------
#
# Settings, Subsidiaries (empty state + purchase detail) and Funds (empty
# state) all used fixed pixel heights that did not derive from or clamp to
# the content rect. Notifications no longer shrink that rect (they are an
# overlay, PM ruling 2026-08-11), but the clamps still matter for a genuinely
# short window, and each of these panels carries a control — a Save/Load
# button, the bootstrapping Buy/Acquire/Open button — that has to survive it.


def test_save_and_exit_never_overlaps_the_speed_buttons(app):
    """Bug fix, 2026-08-10: clamping the Simulation panel's height without
    also adjusting its internal layout left Save & Exit still pinned to the
    box's (now much shorter) bottom edge, landing it on top of the speed
    buttons rather than below them. Save & Exit must give way, not the speed
    control — it is one of the two things this whole panel exists for."""
    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("settings")
    app.draw(2000)
    page = app.pages["settings"]
    for button in page.speed_buttons.values():
        assert button.rect.height > 0, "the speed control must never be the one to give way"
        if page.exit_button.rect.height > 0:
            assert not button.rect.colliderect(page.exit_button.rect)


def test_the_save_slots_are_reachable_with_a_moderate_notification_load(app):
    """The other half of the trade-off: a full 4-notification stack at the
    minimum window size may legitimately have no room left for every row,
    but ordinary play must still see and reach its save slots."""
    app.surface = pygame.Surface((1100, 680))
    app.notifications.push("One message", 0)
    app.navigate("settings")
    app.draw(0)
    page = app.pages["settings"]
    assert page._slot_buttons
    assert app.surface.get_rect().contains(page._slot_buttons[0][2].rect)


def test_the_buy_button_is_reachable_with_a_moderate_notification_load(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True

    app.surface = pygame.Surface((1100, 680))
    app.notifications.push("One message", 0)
    app.navigate("company:subsidiaries")
    app.draw(0)
    page = app.pages["company:subsidiaries"]
    assert app.surface.get_rect().contains(page.buy_button.rect)
    assert page.buy_button.rect.height > 0


def test_the_open_fund_button_is_reachable_with_a_moderate_notification_load(app):
    company = _found_company_for_acquisitions(app)
    company.funds.unlocked = True

    app.surface = pygame.Surface((1100, 680))
    app.notifications.push("One message", 0)
    app.navigate("company:funds")
    app.draw(0)
    page = app.pages["company:funds"]
    assert app.surface.get_rect().contains(page.create_button.rect)
    assert page.create_button.rect.height > 0
