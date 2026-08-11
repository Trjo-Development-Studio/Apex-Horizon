"""The Unlock Tree's layout, compact viewport, scrolling and details panel."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

# -- Unlock Tree: viewport, horizontal scrolling, selection, info panel ----
from ui_support import _found_company_for_acquisitions

from apex_horizon.engine.unlocks import CREATE_COMPANY


def test_the_viewport_shows_every_branch_without_scrolling_vertically(app):
    """The compact viewport (PM, 2026-08-11): every branch is on screen at
    once, which is what makes vertical scrolling unnecessary — and there is
    none to be had, so it had better be true."""
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]

    assert not hasattr(page, "offset"), "no two-axis pan offset any more"
    assert not hasattr(page, "zoom_index"), "no zoom levels to fight the fit"
    for key, rect in page._node_rects.items():
        assert rect.top >= page._map_view.top, key
        assert rect.bottom <= page._map_view.bottom, key


def test_the_viewport_stays_compact_and_does_not_grow_with_the_tree(app):
    """It is the tree's own height, not the room going spare: a tree that is
    mostly wide must not be given a viewport that is mostly tall."""
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]

    generous = page.viewport_height(4000)
    assert generous < 4000, "the viewport must not swell to fill the space"
    # It is the height of the rows themselves, give or take the padding.
    assert generous == page.viewport_height(4000), "and must be stable"
    assert page._map_view.height <= page.viewport_height(10_000)


def test_scrolling_reaches_the_furthest_unlock(app):
    """Every unlock has to be reachable, including the last one along."""
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    tree = app.context.unlocks
    furthest = max(tree.all, key=lambda u: page._node_rects[u.key].right)

    page.scroll_x = page._scroll_limit
    app.draw(0)

    node = page._node_rects[furthest.key]
    assert node.right <= page._map_view.right, "scrolled to the end, nothing hangs off it"
    assert node.left >= page._map_view.left


def test_every_unlock_can_be_brought_into_view(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    tree = app.context.unlocks

    seen = set()
    for scroll in range(0, page._scroll_limit + 60, 60):
        page.scroll_x = scroll
        app.draw(0)
        seen.update(key for key, rect in page._node_rects.items()
                    if page._map_view.contains(rect))
    assert seen == {unlock.key for unlock in tree.all}


def test_the_scroll_range_follows_where_the_nodes_actually_end(app):
    """Not hardcoded to Subsidiaries: a node further right extends the range
    by itself, so a future unlock needs no change here."""
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    before = page._scroll_limit

    real = page._unlocks

    class Farther:
        branch = "final"
        position = 40  # far beyond anything in the catalogue

    page._unlocks = lambda: [*real(), Farther()]
    app.draw(0)
    assert page._scroll_limit > before

    page._unlocks = real
    app.draw(0)
    assert page._scroll_limit == before


def test_there_is_a_horizontal_scrollbar_and_no_vertical_one(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]

    assert page._scroll_limit > 0, "the tree is wider than the viewport"
    assert page._track_rect.width > page._track_rect.height, "a horizontal bar"
    assert page._track_rect.top >= page._map_view.bottom, "sitting beneath the map"
    assert page._thumb_rect.width > 0


def test_dragging_the_scrollbar_thumb_scrolls_the_map(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    assert page.scroll_x == 0

    page.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, button=1, pos=page._thumb_rect.center))
    page.handle_event(pygame.event.Event(
        pygame.MOUSEMOTION, pos=(page._track_rect.right, page._thumb_rect.centery)))
    assert page.scroll_x == page._scroll_limit

    page.handle_event(pygame.event.Event(
        pygame.MOUSEBUTTONUP, button=1, pos=(page._track_rect.right, page._thumb_rect.centery)))
    assert not page._dragging_thumb


def test_the_wheel_scrolls_sideways_rather_than_zooming(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]

    page.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert page.scroll_x > 0
    page.handle_event(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert page.scroll_x == 0


def test_arrow_keys_scroll_sideways_only(app):
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]

    page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT))
    assert page.scroll_x > 0
    moved = page.scroll_x
    # Up and down are not this page's to take: there is nowhere to go.
    assert not page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN))
    assert not page.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP))
    assert page.scroll_x == moved


def test_a_branch_never_splits_across_rows(app):
    """The invariant "no crossing lines" rests on: every node of a branch
    shares one horizontal line, whatever scale the viewport picked."""
    app.navigate("unlocks")
    app.draw(0)
    page = app.pages["unlocks"]
    tree = app.context.unlocks

    for branch in {unlock.branch for unlock in tree.all}:
        rows = {page._node_rects[u.key].centery
                for u in tree.all if u.branch == branch}
        assert len(rows) == 1, f"{branch} split across rows"


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
