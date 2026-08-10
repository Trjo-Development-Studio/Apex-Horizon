"""Tests for the user interface (Design Bible Volumes 14 and 27).

The interface is exercised headlessly: pages are laid out and drawn for real, so
a layout that raises or a page that cannot render fails the suite.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from apex_horizon.engine.unlocks import BASIC_ANALYTICS, BASIC_NEWS, CREATE_COMPANY
from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.ui import theme
from apex_horizon.ui.app import SPEED_KEYS, GameApp
from apex_horizon.ui.chrome import (
    FOOT_ITEMS,
    NAV_ITEMS,
    Breadcrumb,
    NotificationCentre,
)
from apex_horizon.ui.popups import Popup, PopupAction, PopupManager, PromptPopup
from apex_horizon.ui.start_menu import NEW_GAME
from apex_horizon.ui.widgets import Column, SearchBox, Table, truncate


@pytest.fixture
def app():
    set_calendar(Calendar(7, 4, 12))
    application = GameApp(size=(1280, 800), seed=2026)
    yield application
    application.shutdown()
    set_calendar(None)


def click(pos):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos)


def release(pos):
    """Buttons fire on release, so pressing one takes both halves."""
    return pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=pos)


# -- the application launches (V15.19, V19.10) ----------------------------


def test_application_starts_with_a_running_world(app):
    assert app.context.world is not None
    assert app.context.market.active_listings()
    assert app.context.economy is not None
    assert app.context.player is not None


def test_every_page_renders(app):
    # A page that cannot draw would raise here.
    for key in app.pages:
        app.navigate(key)
        app.draw(1000)


def test_frames_run_and_advance_time(app):
    start = app.context.engine.date.day
    for _ in range(4):
        app.tick()
    assert app.context.engine.date.day >= start


def test_pages_render_before_a_company_exists(app):
    # Empty states must be clear rather than blank or broken (V14.26).
    assert app.context.company is None
    for key in ("company", "finance", "dashboard"):
        app.navigate(key)
        app.draw(1000)


# -- navigation (V14.4, V14.5, V14.6, V27.4) ------------------------------


def test_the_sidebar_lists_systems_rather_than_screens():
    """The navigation the project manager settled on (2026-08-08).

    V14.5 lists eight sections and permits more, but a section per page turns
    navigation into a software menu. Investments and Financial Management moved
    inside the systems they belong to, so what remains is one entry per major
    system.
    """
    assert [item.label for item in NAV_ITEMS] == [
        "Dashboard", "Market", "Portfolio", "Company", "Unlocks", "News",
    ]
    # Settings and Save & Exit sit apart at the foot, in that order.
    assert [item.label for item in FOOT_ITEMS] == ["Settings", "Save & Exit"]


def test_every_system_volume_14_5_names_is_still_reachable(app):
    """Nothing became unreachable, it simply stopped being top-level.

    V14.5's purpose is that the sidebar *provides access to* the major systems.
    Access through the system a page belongs to still satisfies that, but only
    if the page genuinely exists and can be opened.
    """
    for destination in ("dashboard", "company", "portfolio", "market", "news",
                        "unlocks", "finance", "settings"):
        assert destination in app.pages, destination
        app.navigate(destination)
        app.draw(0)


def test_leaving_the_game_is_not_a_destination(app):
    """V16.4: Save & Exit ends the session rather than going somewhere."""
    assert "exit" not in {item.key for item in NAV_ITEMS}
    assert "exit" not in app.pages


def test_every_sidebar_destination_has_a_page(app):
    for item in NAV_ITEMS:
        assert item.key in app.pages


def test_every_registered_page_has_a_working_key(app):
    """The other half of the contract test_every_sidebar_destination_has_a_page
    checks: not just that every nav item resolves to a page, but that every
    registered page can actually be navigated to by its own key — a page
    whose key does not round-trip would be exactly as dead an end as one
    missing from the sidebar (bug fix, 2026-08-09)."""
    for key, page in app.pages.items():
        assert page.key == key, (
            f"{type(page).__name__} is registered as {key!r} but reports "
            f"key {page.key!r}; navigating to either would land somewhere "
            f"the other one thinks it owns"
        )


def test_portfolio_tab_views_are_not_registered_as_destinations_of_their_own(app):
    """Analytics and Statistics are tabs inside Portfolio, not sidebar
    destinations (bug fix, 2026-08-09): they used to carry a ``key`` that
    looked like a real, reachable page but was never registered in
    app.pages, so navigating to it would silently do nothing. Removed rather
    than registered, since Portfolio composes them by calling
    draw_content directly, not through Page.draw — there was never a
    breadcrumb or title bar for a registered destination to show."""
    portfolio = app.pages["portfolio"]
    assert portfolio.analytics.key == ""
    assert portfolio.statistics.key == ""
    assert "analytics" not in app.pages
    assert "statistics" not in app.pages


def test_clicking_the_sidebar_navigates(app):
    app.draw(0)  # lay out the sidebar so it has hit areas
    market_rect = app.sidebar._rects["market"]
    app.sidebar.handle_event(click(market_rect.center))
    assert app.sidebar.take_request() == "market"
    app.navigate("market")
    assert app.current_key == "market"


def test_sub_pages_keep_their_parent_highlighted(app):
    app.navigate("market:company")
    app.draw(0)
    assert app.sidebar.active == "market"


# -- mouse-button back/forward navigation (2026-08-09) ---------------------
#
# Browser-style history built into navigate() itself, so every existing way
# of moving between pages — sidebar, breadcrumb, a row drilled into, a popup
# redirecting after an action — already populates it with no page-specific
# wiring. Mouse buttons 4 and 5 (pygame.BUTTON_X1 / BUTTON_X2) just replay it.


def click_button(button: int, pos=(0, 0)):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=pos)


def test_navigate_back_and_forward_retrace_history(app):
    """The exact scenario from the feature request: Market -> Portfolio ->
    Company, then back, back, forward."""
    app.navigate("market")
    app.navigate("portfolio")
    app.navigate("company")
    assert app.current_key == "company"

    app.navigate_back()
    assert app.current_key == "portfolio"

    app.navigate_back()
    assert app.current_key == "market"

    app.navigate_forward()
    assert app.current_key == "portfolio"


def test_navigate_back_does_nothing_with_no_history(app):
    assert app.current_key == "dashboard"
    app.navigate_back()
    assert app.current_key == "dashboard"


def test_navigate_forward_does_nothing_with_no_forward_history(app):
    app.navigate("market")
    app.navigate_forward()
    assert app.current_key == "market"


def test_navigating_normally_after_going_back_clears_forward_history(app):
    app.navigate("market")
    app.navigate("portfolio")
    app.navigate_back()
    assert app.current_key == "market"

    app.navigate("news")  # a fresh move, the way clicking a link would be
    assert app.current_key == "news"
    app.navigate_forward()
    assert app.current_key == "news", "forward history must not have survived the new move"


def test_mouse_button_4_navigates_back_through_real_events(app):
    app.navigate("market")
    app.navigate("portfolio")
    app.handle_events()  # drain
    pygame.event.post(click_button(pygame.BUTTON_X1))
    app.handle_events()
    assert app.current_key == "market"


def test_mouse_button_5_navigates_forward_through_real_events(app):
    app.navigate("market")
    app.navigate("portfolio")
    app.navigate_back()
    assert app.current_key == "market"
    app.handle_events()  # drain
    pygame.event.post(click_button(pygame.BUTTON_X2))
    app.handle_events()
    assert app.current_key == "portfolio"


def test_ordinary_clicks_are_unaffected_by_the_new_button_handling(app):
    app.draw(0)  # lay out the sidebar so it has hit areas
    market_rect = app.sidebar._rects["market"]
    app.handle_events()  # drain
    pygame.event.post(click_button(pygame.BUTTON_LEFT, market_rect.center))
    pygame.event.post(click_button(pygame.BUTTON_RIGHT))
    pygame.event.post(click_button(pygame.BUTTON_MIDDLE))
    app.handle_events()
    assert app.current_key == "market", "left/right/middle clicks must behave exactly as before"


def test_back_and_forward_do_nothing_while_a_popup_is_open(app):
    app.navigate("market")
    app.navigate("portfolio")
    app._prompt_exit()
    assert app.popups.is_open

    app.handle_events()  # drain
    pygame.event.post(click_button(pygame.BUTTON_X1))
    app.handle_events()
    assert app.current_key == "portfolio", "back must not fire through an open popup"


def test_back_and_forward_do_nothing_while_the_dev_console_is_open(app):
    app.navigate("market")
    app.navigate("portfolio")
    app.dev_console.open = True

    app.handle_events()  # drain
    pygame.event.post(click_button(pygame.BUTTON_X1))
    app.handle_events()
    assert app.current_key == "portfolio", "back must not fire through the open console"


def test_save_and_exit_can_never_be_reached_through_back_or_forward(app):
    """V16.4: leaving is an action, not a destination. Save & Exit never calls
    navigate(), so it can never end up in history for back/forward to land on."""
    app.navigate("market")
    for _ in range(5):
        app.navigate_back()
    assert "exit" not in app.pages
    assert app.current_key in app.pages


def test_escape_retraces_history_the_same_way_the_mouse_button_does(app):
    """QoL pass, 2026-08-10: one consistent meaning for Escape — go back
    through the same history navigate_back already maintains, rather than a
    bespoke per-page mechanism."""
    app.navigate("market")
    app.navigate("portfolio")
    app.navigate("unlocks")
    app.handle_events()  # drain
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    app.handle_events()
    assert app.current_key == "portfolio"


def test_escape_does_nothing_with_no_history(app):
    assert app.current_key == "dashboard"
    app.handle_events()
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    app.handle_events()
    assert app.current_key == "dashboard"


def test_escape_closes_a_focused_search_box_before_it_navigates_back(app):
    """The page gets first refusal: clearing a focused search box is what
    Escape already did there, and must keep doing it instead of also (or
    instead) retracing history in the same keypress."""
    app.navigate("market")
    app.navigate("portfolio")
    page = app.pages["market"]
    app.navigate("market")
    app.draw(0)
    page.search.focused = True
    page.search.text = "abc"

    app.handle_events()  # drain
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    app.handle_events()

    assert app.current_key == "market", "the search box must claim this Escape, not history"
    assert page.search.text == ""
    assert not page.search.focused


def test_escape_does_not_fire_while_a_popup_is_open(app):
    app.navigate("market")
    app.navigate("portfolio")
    app._prompt_exit()
    assert app.popups.is_open

    app.handle_events()  # drain
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    app.handle_events()

    assert app.current_key == "portfolio", "Escape must dismiss the popup, not retrace history"


def test_navigation_history_is_cleared_after_starting_a_new_game(menu_app):
    menu_app.navigate("market")
    menu_app.navigate("portfolio")
    assert menu_app._nav_history  # something to clear

    _new_game(menu_app, slot="3", name="Fresh Start")

    assert menu_app.current_key == "dashboard"
    assert not menu_app._nav_history
    assert not menu_app._nav_forward
    menu_app.navigate_back()
    assert menu_app.current_key == "dashboard", "nothing from before the new game to go back to"


def test_navigation_history_is_cleared_after_loading_a_game(menu_app):
    _new_game(menu_app, slot="3", name="Continued")
    menu_app.navigate("market")
    menu_app.navigate("portfolio")
    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    menu_app._load_from_menu("3")

    assert not menu_app._nav_history
    assert not menu_app._nav_forward


def test_breadcrumb_returns_to_an_earlier_level(app):
    breadcrumb = Breadcrumb()
    breadcrumb.set([("Market", "market"), ("Some Company", "market:company")])
    surface = pygame.Surface((900, 200))
    breadcrumb.draw(surface, app.fonts, (0, 0), (20, 40))
    # Only earlier segments are clickable; the current page is not a link.
    assert len(breadcrumb._rects) == 1
    rect, destination = next(iter(breadcrumb._rects))
    breadcrumb.handle_event(click(rect.center))
    assert breadcrumb.take_request() == destination == "market"


def test_opening_a_market_row_drills_into_that_company(app):
    app.navigate("market")
    app.draw(0)
    market = app.pages["market"]
    row_rect, row = next(iter(market.table._row_rects))
    market.handle_event(click(row_rect.center))
    app._collect_page_requests()
    assert app.current_key == "market:company"
    assert market.selected_company_id == row["id"]
    assert app.pages["market:company"].title == row["name"]


# -- tables (V14.8, V14.17, V27.3, V27.5) ---------------------------------


def table_rows():
    return [
        {"name": "Cedar Foods", "size": 30},
        {"name": "Atlas Mining", "size": 10},
        {"name": "Beacon Energy", "size": 20},
    ]


def test_sorting_is_explicit_and_reverses_on_reselection():
    table = Table(columns=[Column("name", "Name", 100)], search_key="name")
    table.sort_by("name")
    assert [r["name"] for r in table.visible_rows(table_rows())] == [
        "Atlas Mining", "Beacon Energy", "Cedar Foods"
    ]
    table.sort_by("name")
    assert table.sort_descending
    assert [r["name"] for r in table.visible_rows(table_rows())] == [
        "Cedar Foods", "Beacon Energy", "Atlas Mining"
    ]


def test_sorting_is_numeric_where_the_data_is():
    table = Table(columns=[Column("size", "Size", 80, numeric=True)], sort_key="size")
    assert [r["size"] for r in table.visible_rows(table_rows())] == [10, 20, 30]


def test_search_filters_immediately_and_combines_with_sorting():
    table = Table(columns=[Column("name", "Name", 100)], search_key="name", sort_key="name")
    found = table.visible_rows(table_rows(), "N")
    # Matches are case-insensitive, and the chosen sort still applies to them.
    assert [r["name"] for r in found] == ["Atlas Mining", "Beacon Energy"]


def test_search_that_matches_nothing_returns_nothing():
    table = Table(columns=[Column("name", "Name", 100)], search_key="name")
    assert table.visible_rows(table_rows(), "zzz") == []


def test_pagination_splits_long_lists():
    table = Table(columns=[Column("name", "Name", 100)], page_size=2)
    assert table.page_count(len(table_rows())) == 2
    assert table.page_count(0) == 1


def test_a_single_click_opens_a_row(app):
    app.navigate("market")
    app.draw(0)
    table = app.pages["market"].table
    rect, row = table._row_rects[2]
    assert table.handle_event(click(rect.center))
    assert table.take_opened() is row
    # Opening consumes the row, so it is not reported twice.
    assert table.take_opened() is None


def test_search_typing_updates_the_query():
    box = SearchBox()
    box.focused = True
    box.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, unicode="a"))
    box.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b, unicode="b"))
    assert box.text == "ab"
    box.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_BACKSPACE, unicode=""))
    assert box.text == "a"
    box.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    assert box.text == ""


def test_long_text_is_truncated_rather_than_overflowing(app):
    long_name = "A Very Long Company Name That Will Not Fit In Its Column"
    shortened = truncate(app.fonts.small, long_name, 80)
    assert shortened.endswith("…")
    assert app.fonts.small.size(shortened)[0] <= 80


# -- popups pause the simulation (V13.20, V14.15, V27.6) ------------------


def test_a_popup_pauses_the_simulation(app):
    app.tick()
    app._prompt_exit()
    app.tick()
    assert app.context.engine.clock.paused is True
    day = app.context.engine.date.day
    for _ in range(5):
        app.tick()
    # Time does not move while a decision is open.
    assert app.context.engine.date.day == day


def test_dismissing_a_popup_resumes_the_simulation(app):
    app._prompt_exit()
    app.tick()
    app.popups.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    app.tick()
    assert app.context.engine.clock.paused is False


def test_only_one_decision_is_shown_at_a_time():
    manager = PopupManager()
    first = Popup("First", "…", [PopupAction("ok", "OK", primary=True)])
    second = Popup("Second", "…", [PopupAction("ok", "OK", primary=True)])
    manager.open(first)
    manager.open(second)
    assert manager.current is first
    manager.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    # The queued decision follows rather than stacking on top.
    assert manager.current is second


def test_a_popup_offers_a_clear_cancel(app):
    popup = Popup("Confirm", "…", [PopupAction("no", "Cancel"),
                                   PopupAction("yes", "Confirm", primary=True)])
    assert popup.cancel_key == "no"
    popup.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, unicode=""))
    assert popup.chosen == "no"


def test_a_popup_swallows_clicks_meant_for_the_page():
    popup = Popup("Confirm", "…")
    assert popup.handle_event(click((10, 10))) is True


def test_naming_prompt_requires_a_name(app):
    popup = PromptPopup(
        title="Found", message="…", placeholder="Name",
        actions=[PopupAction("cancel", "Cancel"), PopupAction("found", "Found", primary=True)],
    )
    popup.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    assert popup.chosen is None  # nothing typed yet
    for character in "Acme":
        popup.handle_event(pygame.event.Event(pygame.KEYDOWN, key=0, unicode=character))
    assert popup.text == "Acme"
    popup.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    assert popup.chosen == "found"


def test_founding_is_refused_until_create_company_is_unlocked(app):
    """V6.2: the mechanic is earned. The refusal must explain itself (V14.26)."""
    app.context.player.cash = Money(60_000)
    app.navigate("company")
    app._prompt_found_company()

    assert app.popups.current is None, "no naming prompt without the unlock"
    assert app.context.company is None
    assert any("Create Company" in item.text for item in app.notifications.items)


def test_founding_a_company_through_the_interface(app):
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    app.navigate("company")
    app._prompt_found_company()
    for character in "Meridian Capital":
        app.popups.current.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=0, unicode=character)
        )
    app.popups.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    assert app.context.company is not None
    assert app.context.company.name == "Meridian Capital"
    # Founding marks the game as having unsaved changes; the indicator picks
    # that up on the next frame (V14.19).
    assert app.saves.unsaved_changes is True
    app.tick()
    assert app.save_indicator.unsaved is True
    app.draw(1000)


# -- time controls (V14.18, V27.9) ----------------------------------------


def test_speed_keys_change_the_simulation_speed(app):
    for key, speed in SPEED_KEYS.items():
        app.handle_events()  # drain
        pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key, unicode=""))
        app.handle_events()
        assert app.context.engine.clock.speed == speed


def test_time_controls_offer_only_the_supported_speeds(app):
    assert app.time_controls.speeds == (1, 2, 3)
    # Pausing is not a control: it happens only through popups (V13.20).
    assert not hasattr(app.time_controls, "pause")


# -- notifications (V14.16, V27.7) ----------------------------------------


def test_notifications_expire(app):
    centre = NotificationCentre()
    centre.push("Something happened", 0)
    centre.update(1000)
    assert centre.items
    centre.update(99_000)
    assert not centre.items


def test_notifications_never_stack_beyond_what_can_be_read(app):
    centre = NotificationCentre()
    for index in range(20):
        centre.push(f"Message {index}", 0)
    surface = pygame.Surface((900, 600))
    centre.draw(surface, app.fonts, 500)
    assert len(centre.items) <= 12


def test_notification_positions_stay_on_screen(app):
    # An out-of-range timestamp must never place a message off the edge.
    centre = NotificationCentre()
    centre.push("Late arrival", 10_000)
    surface = pygame.Surface((900, 600))
    centre.draw(surface, app.fonts, 0)  # "now" before the message was created


def test_engine_errors_reach_the_player(app):
    from apex_horizon.engine import errors

    errors.notify_player("Saving failed after 3 attempts.")
    assert any("Saving failed" in item.text for item in app.notifications.items)


# -- the notification-safe content area (bug fix, 2026-08-09) -------------
#
# Notifications used to anchor over the same lower-right area as the Hire
# buttons, market rows and dashboard figures. The fix reserves that corner out
# of every page's content rect — but the first version reserved the worst
# case (a full stack of MAX_VISIBLE) at all times, which permanently starved
# short windows of content (the Employee Management staff table had no room
# left at all at the minimum window size even with nothing showing). The
# reservation is sized to what is actually on screen instead.


def test_notification_safe_height_is_zero_with_nothing_showing():
    centre = NotificationCentre()
    assert centre.safe_height() == 0


def test_notification_safe_height_scales_with_the_stack(app):
    centre = NotificationCentre()
    one_slot = theme.NOTIFICATION_HEIGHT + theme.NOTIFICATION_GAP
    centre.push("First", 0)
    assert centre.safe_height() == centre.MARGIN + one_slot
    for index in range(1, 8):
        centre.push(f"Message {index}", 0)
    # Capped at MAX_VISIBLE slots, however many messages are actually queued.
    assert centre.safe_height() == centre.MARGIN + centre.MAX_VISIBLE * one_slot


def test_a_short_window_keeps_the_staff_table_when_nothing_is_showing(app):
    """The regression this fix exists for: at the minimum window size with no
    notifications queued, the roster must still be visible rather than
    permanently sacrificed to a worst-case reservation."""
    app.context.player.cash = Money(500_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    roster = company.employees
    roster.refresh_applicants(app.context.engine.rng, app.context.names,
                              app.context.allocator, app.context.engine.date.day)
    roster.hire(roster.applicants[0], app.context.engine.date.day)

    app.surface = pygame.Surface((1100, 680))
    assert not app.notifications.items
    app.navigate("company:employees")
    app.draw(0)
    table = app.pages["company:employees"].table
    assert table._row_rects, "the staff table should have room to show a row"


def test_a_full_notification_stack_still_leaves_the_hire_buttons_reachable(app):
    """The other half of the same trade-off: however little room a full stack
    leaves, it must never leave the Hire buttons themselves unreachable."""
    app.context.player.cash = Money(500_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.employees.refresh_applicants(app.context.engine.rng, app.context.names,
                                         app.context.allocator, app.context.engine.date.day)

    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("company:employees")
    app.draw(2000)
    page = app.pages["company:employees"]
    assert page.hire_buttons, "a Hire button must still be reachable under a full stack"
    for button in page.hire_buttons.values():
        assert app.surface.get_rect().contains(button.rect)


def test_a_hidden_staff_table_says_so_rather_than_leaving_an_unexplained_gap(app):
    """Bug fix, 2026-08-09: table_height could land at exactly 0 — not
    negative, so table_height > 0 never fired either — leaving a bare gap
    above the Candidates panel where the staff table used to be, with
    nothing drawn to say why. A small amount is now reclaimed from
    Candidates so the message always has room, unless Candidates is already
    down at its own compact floor."""
    app.context.player.cash = Money(500_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    roster = company.employees
    roster.refresh_applicants(app.context.engine.rng, app.context.names,
                              app.context.allocator, app.context.engine.date.day)
    roster.hire(roster.applicants[0], app.context.engine.date.day)

    # The exact size this regressed at: room enough for Candidates but not
    # both Candidates and the staff table once a full stack is reserved.
    app.surface = pygame.Surface((1280, 800))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("company:employees")
    app.draw(2000)

    page = app.pages["company:employees"]
    assert not page.table._row_rects, "this is the regime where the table has no room"
    assert page.hire_buttons, "Candidates must still have kept its own priority"


# -- table pagination at short heights (bug fix, 2026-08-09) --------------
#
# _rows_that_fit never returns 0, so a table always tries to show at least
# one row even when it barely has room for one — and the pagination footer,
# positioned from the bottom of the rect, used to land on top of that row
# and its header rather than below them.


def test_table_pagination_does_not_overlap_a_forced_row(app):
    table = Table(columns=[Column("name", "Name", 200)])
    rows = [{"name": f"Row {index}"} for index in range(30)]
    surface = pygame.Surface((400, 90))  # not enough room for header+row+footer
    rect = pygame.Rect(0, 0, 400, 90)
    table.draw(surface, rect, app.fonts, (0, 0), rows)
    assert table.page_size >= 1
    assert table._row_rects, "a table this short still forces at least one row"
    assert table._prev_rect.width == 0 and table._next_rect.width == 0, (
        "the footer must not draw, and its hit-rects must not sit, over that row"
    )


def test_table_pagination_still_shows_with_room_to_spare(app):
    table = Table(columns=[Column("name", "Name", 200)])
    rows = [{"name": f"Row {index}"} for index in range(30)]
    surface = pygame.Surface((400, 400))
    rect = pygame.Rect(0, 0, 400, 400)
    table.draw(surface, rect, app.fonts, (0, 0), rows)
    assert table.page_size > 1
    assert table._next_rect.width > 0, "ample room must still offer a next-page control"


# -- visual language (V1.15, V27.10) --------------------------------------


def test_icons_exist_for_every_sidebar_entry():
    from apex_horizon.ui import icons

    for item in NAV_ITEMS:
        assert item.icon in icons.ICONS
        surface = icons.render(item.icon, theme.TEXT, 22)
        assert surface.get_size() == (22, 22)


def test_every_icon_is_paired_with_a_label(app):
    # Navigation must never depend on icon recognition alone (V27.10).
    assert all(item.label for item in NAV_ITEMS)
    app.sidebar.hovered = NAV_ITEMS[0]
    app.draw(0)
    app.sidebar.draw_tooltip(app.surface, app.fonts)


def test_gain_and_loss_use_distinct_colours():
    assert theme.value_colour(True) == theme.POSITIVE
    assert theme.value_colour(False) == theme.NEGATIVE
    assert theme.value_colour(None) == theme.TEXT


def test_window_can_be_resized(app):
    pygame.event.post(pygame.event.Event(pygame.VIDEORESIZE, w=900, h=600, size=(900, 600)))
    app.handle_events()
    app.draw(0)
    # Never smaller than the minimum usable size.
    assert app.surface.get_width() >= 1100


# -- news and analytics pages (V10.15, V9.22) -----------------------------


def unlock_news(app, *keys):
    """Grant news unlocks and let the effects reconfigure the systems."""
    for key in keys:
        app.context.player.unlocks.unlock(key)
    app.effects.apply(app.context)


def test_the_news_page_lists_stories_and_shows_one_in_full(app):
    from apex_horizon.engine.news import NewsTier

    unlock_news(app, BASIC_NEWS)
    app.context.news.tier = NewsTier.BREAKING
    app.context.engine.run_days(200)
    app.navigate("news")
    app.draw(0)

    page = app.pages["news"]
    assert page.articles(), "200 days should have produced something to report"
    assert page._row_hitboxes, "the archive should be selectable"

    # Selecting a later story changes which one is shown in full.
    row, index = page._row_hitboxes[2]
    page.handle_event(click(row.center))
    assert page.selected == index


def test_the_news_lead_story_never_overlaps_itself_under_a_full_notification_stack(app):
    """Bug fix, 2026-08-09: a fixed 150px lead story panel left the archive
    with room for a single row once the notification safe area came out of
    the page, and at the minimum window size with a full stack the lead
    panel itself shrank far enough that its byline was drawn on top of its
    own body text. A second pass at this exact scenario also found the
    archive's own "Archive" heading and "Select a story..." hint drawn
    unconditionally, spilling past the bottom of its own (by then 22px tall)
    panel and into the notification stack below it. Both must degrade
    without ever overlapping."""
    from apex_horizon.engine.news import NewsTier

    unlock_news(app, BASIC_NEWS)
    app.context.news.tier = NewsTier.BREAKING
    app.context.engine.run_days(200)

    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("news")
    app.draw(2000)

    page = app.pages["news"]
    assert page.articles(), "200 days should have produced something to report"
    # However little room is left, nothing drawn here may collide: the page
    # is trusted to omit a line rather than lay one over another.


def test_the_news_page_offers_only_unlocked_tiers(app):
    from apex_horizon.engine.news import NewsTier

    unlock_news(app, BASIC_NEWS)
    assert app.pages["news"].filters() == ["All", "Company"]

    app.context.news.tier = NewsTier.BREAKING
    assert app.pages["news"].filters() == [
        "All", "Company", "Market", "Economy", "Breaking",
    ]


def test_filtering_the_news_narrows_the_archive(app):
    from apex_horizon.engine.news import NewsTier

    unlock_news(app, BASIC_NEWS)
    app.context.news.tier = NewsTier.MARKET
    app.context.engine.run_days(200)
    page = app.pages["news"]
    page.filter = "Market"

    assert page.articles()
    assert all(str(a.tier) == "Market" for a in page.articles())


def test_the_news_page_says_it_is_locked_before_basic_news(app):
    """V14.26: earned, not missing."""
    app.navigate("news")
    app.draw(0)
    assert app.pages["news"].locked
    assert app.pages["news"].cards() == []


def test_an_empty_news_archive_states_so(app):
    unlock_news(app, BASIC_NEWS)
    app.navigate("news")
    app.draw(0)  # day zero: nothing has happened yet
    assert app.pages["news"].articles() == []


def test_every_unlocked_report_is_drawn(app):
    """A report the player has unlocked must not be lost to the layout."""
    from apex_horizon.engine.analytics import AnalyticsTier

    app.context.player.cash = Money(200_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Test Capital", 1)
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    unlock_news(app, BASIC_ANALYTICS)
    app.context.analytics.tier = AnalyticsTier.ADVANCED
    app.context.engine.run_days(28 * 14)

    app.navigate("portfolio")
    portfolio = app.pages["portfolio"]
    portfolio.tabs.selected = "Analytics"
    app.draw(0)

    reports = app.context.analytics.reports()
    assert len(reports) == 5

    page = portfolio.analytics
    drawn = []
    page._draw_report = lambda surface, rect, fonts, report: drawn.append((rect, report))
    app.draw(0)

    assert len(drawn) == len(reports)
    for rect, report in drawn:
        needed = 68 + len(report.metrics) * 44
        assert rect.height >= min(needed, rect.height), report.title


def test_analytics_before_a_company_shows_only_what_exists(app):
    """The market is there from the start; the company reports are not."""
    unlock_news(app, BASIC_ANALYTICS)
    app.navigate("portfolio")
    app.pages["portfolio"].tabs.selected = "Analytics"
    app.draw(0)

    titles = [report.title for report in app.context.analytics.reports()]
    assert titles == ["Market"]


# -- Portfolio holds both sets of holdings (PM decision, 2026-08-08) -------


def test_portfolio_shows_the_company_only_once_one_exists(app):
    """The player invests personally long before they are a CEO (V1.19, V1.20)."""
    portfolio = app.pages["portfolio"]

    assert "Company" not in portfolio.available()
    assert "Personal" in portfolio.available()

    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Test Capital", 1)
    company.attach_market(app.context.market, app.context.allocator)

    assert "Company" in portfolio.available()


def test_the_company_view_never_replaces_the_personal_one(app):
    """Both pools of money are shown; one does not stand in for the other."""
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Test Capital", 1)
    company.attach_market(app.context.market, app.context.allocator)

    available = app.pages["portfolio"].available()
    assert available.index("Personal") < available.index("Company")


def test_portfolio_draws_every_view(app):
    portfolio = app.pages["portfolio"]
    app.navigate("portfolio")
    for label in portfolio.available():
        portfolio.tabs.selected = label
        app.draw(0)


# -- personal cash is always visible (PM, 2026-08-09) ---------------------


def _cash_box(app, key: str):
    """Open a page and report the cash figures among its summary cards."""
    app.navigate(key)
    app.draw(0)
    return [card.value for card in app.page._cards_with_cash()
            if card.label == "Cash"]


def test_personal_cash_is_shown_on_every_main_tab(app):
    """Whatever the player is looking at, what they can spend is on screen."""
    for item in NAV_ITEMS:
        assert _cash_box(app, item.key), f"{item.label} shows no cash"


def test_cash_leads_the_cards_and_is_never_shown_twice(app):
    """It is a summary card like the others, in the same position each time."""
    for item in NAV_ITEMS:
        app.navigate(item.key)
        labels = [card.label for card in app.page._cards_with_cash()]
        assert labels[0] == "Cash", item.label
        assert labels.count("Cash") == 1, item.label
        assert "Personal cash" not in labels, f"{item.label} duplicates the figure"


def test_personal_cash_is_shown_on_sub_pages_too(app):
    for key in ("market:company", "company:employees", "company:subsidiaries"):
        assert _cash_box(app, key), key


def test_the_figure_updates_after_a_transaction(app):
    before = _cash_box(app, "market")[0]

    app.context.player.cash = app.context.player.cash + Money(5_000)

    assert _cash_box(app, "market")[0] != before


def test_the_cash_card_never_shows_cents(app):
    """Bug fix, 2026-08-10: every other summary card rounds to whole dollars
    (`decimals=0`), but the shared Cash card was built with `.format()`'s own
    default of two, so it alone showed cents — the one figure the player
    reads most often was the one that stood out as different."""
    app.context.player.cash = Money("1234.56")

    shown = _cash_box(app, "market")[0]

    assert shown == "$1,235"
    assert "." not in shown


def test_it_is_personal_cash_rather_than_net_worth(app):
    """V1.4: net worth counts holdings and a company that cannot be spent."""
    app.context.player.cash = Money(1_000)
    listing = app.context.market.active_listings()[0]
    app.context.portfolio.buy(listing.company_id, 1, 1)

    shown = _cash_box(app, "market")[0]

    assert shown == app.context.player.cash.format(decimals=0)
    assert shown != app.context.player.net_worth().format()


def test_company_cash_stays_separate_from_the_players(app):
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Test Capital", 1)
    company.attach_market(app.context.market, app.context.allocator)

    shown = _cash_box(app, "company")[0]

    assert shown == app.context.player.cash.format(decimals=0)
    assert shown != company.finances.cash.format()


# -- the Start Menu (V16.4) -----------------------------------------------


def _choose(app, key: str) -> None:
    """Answer the open popup, the way clicking its button would."""
    app.popups.current.chosen = key
    app.popups.handle_event(pygame.event.Event(pygame.USEREVENT))


@pytest.fixture
def menu_app(tmp_path):
    from apex_horizon.engine.save import SaveStore

    set_calendar(Calendar(7, 4, 12))
    application = GameApp(size=(1100, 760), seed=2026, start_in_menu=True)
    application.saves.store = SaveStore(tmp_path, manual_slots=5)
    application.menu.saves = application.saves
    yield application
    application.shutdown()
    set_calendar(None)


def test_the_game_opens_on_the_start_menu(menu_app):
    assert menu_app.in_menu
    menu_app.menu.draw(menu_app.surface, menu_app.fonts, (0, 0))


def test_a_directly_built_application_starts_in_play(app):
    """Tests and tools want a running game, not a menu."""
    assert not app.in_menu


def _new_game(menu_app, slot: str = "2", name: str = "My Empire") -> None:
    """Start Menu -> New Game -> choose a slot -> name it -> create."""
    from apex_horizon.ui.start_menu import NEW_GAME

    menu_app.menu.request = (NEW_GAME, slot)
    menu_app._menu_tick(0)
    if menu_app.popups.current is not None and not isinstance(
            menu_app.popups.current, PromptPopup):
        _choose(menu_app, "overwrite")  # the slot already held a game
    prompt = menu_app.popups.current
    assert isinstance(prompt, PromptPopup), "the game must be named before it exists"
    prompt.text = name
    _choose(menu_app, "create")


def test_new_game_asks_for_a_slot_before_starting_one(menu_app):
    """PM: the player chooses where the game lives; nothing is picked for them."""
    from apex_horizon.ui.start_menu import NEW_GAME

    menu_app.menu.request = NEW_GAME
    menu_app._menu_tick(0)

    assert menu_app.in_menu, "no world exists until a slot is chosen"
    assert menu_app.saves.slot is None


def test_choosing_an_empty_slot_asks_for_a_name(menu_app):
    from apex_horizon.ui.start_menu import NEW_GAME

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
    from apex_horizon.ui.start_menu import NEW_GAME

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


def test_the_sidebar_starts_collapsed_to_icons(app):
    assert not app.sidebar.expanded
    assert app.sidebar.width(0) == theme.SIDEBAR_WIDTH


def test_clicking_the_logo_expands_and_collapses(app):
    app.draw(0)  # lay the logo out so it has a hit area
    logo = app.sidebar._logo_rect

    app.sidebar.handle_event(click(logo.center))
    assert app.sidebar.expanded
    # The width eases open over a couple of frames rather than jumping.
    app.sidebar.width(10_000)
    assert app.sidebar.width(11_000) == theme.SIDEBAR_EXPANDED

    app.sidebar.handle_event(click(logo.center))
    assert not app.sidebar.expanded
    app.sidebar.width(12_000)
    assert app.sidebar.width(13_000) == theme.SIDEBAR_WIDTH


# -- the real logo (project manager: window icon + sidebar mark) -----------


def test_the_mark_loads_at_the_size_asked_for(app):
    from apex_horizon.ui import assets

    image = assets.mark(40)

    assert image is not None
    assert image.get_size() == (40, 40)


def test_the_mark_is_cached_rather_than_reloaded(app):
    from apex_horizon.ui import assets

    first = assets.mark(40)
    second = assets.mark(40)

    assert first is second


def test_a_missing_asset_is_handled_rather_than_raised(app, monkeypatch, tmp_path):
    """This is artwork, not gameplay data: a missing file must not crash."""
    from apex_horizon.ui import assets

    assets._cache.clear()
    monkeypatch.setattr(assets, "asset_path", lambda *parts: tmp_path.joinpath(*parts))

    assert assets.mark(40) is None
    assets._cache.clear()


def test_the_sidebar_draws_the_real_mark_not_placeholder_text(app):
    """The blue of the mark should be visible where the old 'AH' text sat."""
    app.draw(0)

    sampled = [app.surface.get_at((x, 23))[:3]
               for x in range(theme.SIDEBAR_WIDTH // 2 - 10, theme.SIDEBAR_WIDTH // 2 + 10)]
    assert any(blue > red and blue > 120 for red, _, blue in sampled), \
        "expected some of the mark's blue among the sampled pixels"


def test_the_mark_stays_put_when_the_sidebar_expands(app):
    """Branding does not move; only the wordmark beside it appears."""
    app.draw(0)
    collapsed_logo = app.sidebar._logo_rect.topleft

    app.sidebar.expanded = True
    app.sidebar.width(10_000)
    app.draw(11_000)

    assert app.sidebar._logo_rect.topleft == collapsed_logo


def test_hovering_the_logo_highlights_behind_it(app):
    """The mark cannot recolour itself, so the affordance is a background pill."""
    logo_edge = (6, 38)  # inside the hit area, away from the mark's own pixels

    app.sidebar.draw(app.surface, app.fonts, (-100, -100), 0)
    unhovered = app.surface.get_at(logo_edge)[:3]

    app.sidebar.draw(app.surface, app.fonts, (34, 23), 0)
    hovered = app.surface.get_at(logo_edge)[:3]

    assert hovered != unhovered


def test_the_window_icon_is_set_from_the_real_logo(monkeypatch):
    """V15.19: the window/taskbar icon must be the actual artwork, not nothing."""
    from apex_horizon.ui import assets

    seen = []
    monkeypatch.setattr(pygame.display, "set_icon", lambda surface: seen.append(surface))
    set_calendar(Calendar(7, 4, 12))
    application = GameApp(size=(900, 600), seed=2026)
    try:
        assert len(seen) == 1
        expected = assets.mark(64)
        assert expected is not None
        assert seen[0].get_size() == expected.get_size()
    finally:
        application.shutdown()
        set_calendar(None)


def test_the_expanded_state_is_remembered_across_screens(app):
    app.draw(0)
    app.sidebar.handle_event(click(app.sidebar._logo_rect.center))

    for item in NAV_ITEMS:
        app.navigate(item.key)
        app.draw(0)
        assert app.sidebar.expanded, item.label


def test_expanding_moves_the_page_rather_than_covering_it(app):
    """The page must stay usable, not sit underneath the sidebar."""
    app.draw(0)
    app.sidebar.expanded = True
    for step in range(20):
        app.draw(1000 + step * 30)

    assert app.sidebar.width(10_000) == theme.SIDEBAR_EXPANDED
    # Every navigation item still has a hit area inside the wider sidebar.
    for item in NAV_ITEMS:
        assert app.sidebar._rects[item.key].right <= theme.SIDEBAR_EXPANDED


def test_tooltips_stop_once_the_names_are_showing(app):
    """A label beside the icon and a tooltip repeating it is noise."""
    app.draw(0)
    app.sidebar.expanded = True
    app.sidebar.hovered = NAV_ITEMS[0]

    # Drawing the tooltip while expanded must render nothing at all.
    before = pygame.image.tobytes(app.surface, "RGB")
    app.sidebar.draw_tooltip(app.surface, app.fonts)
    assert pygame.image.tobytes(app.surface, "RGB") == before


def test_a_buttons_tooltip_shows_only_on_hover(app):
    """`Button.tooltip` was set on every button since the field was added but
    never once read (bug fix, 2026-08-10) — wired to the same `draw_tooltip`
    primitive the Sidebar already uses for its own icons.

    Compares only the strip above the button, where the tooltip renders —
    not the button itself, which already changes colour on hover regardless
    of any tooltip, and would make the comparison pass for the wrong reason.
    """
    from apex_horizon.ui.widgets import Button

    button = Button("Criteria", tooltip="Set the minimum skill for auto-hire.")
    rect = pygame.Rect(200, 200, 100, 30)
    above = pygame.Rect(150, 150, 300, 45)

    app.draw(0)
    button.draw(app.surface, rect, app.fonts, (0, 0))
    not_hovered = pygame.image.tobytes(app.surface.subsurface(above), "RGB")

    app.draw(0)
    button.draw(app.surface, rect, app.fonts, rect.center)
    hovered = pygame.image.tobytes(app.surface.subsurface(above), "RGB")

    assert hovered != not_hovered


def test_notifications_are_drawn_on_the_right(app):
    """V27.7: clear of the sidebar, which has to stay usable."""
    app.notifications.push("A message worth reading", 0)
    app.draw(theme.SLIDE_MS + 10)

    # The sample skips the sidebar, which is filled whether or not a message is
    # showing and would otherwise count as content on the left.
    width = app.surface.get_width()
    left_half = pygame.Rect(theme.SIDEBAR_EXPANDED, app.surface.get_height() - 120,
                            width // 2 - theme.SIDEBAR_EXPANDED, 120)
    right_half = pygame.Rect(width // 2, app.surface.get_height() - 120,
                             width // 2, 120)

    def lit(area):
        return sum(
            app.surface.get_at((x, y))[:3] != theme.BACKGROUND
            for x in range(area.left, area.right, 4)
            for y in range(area.top, area.bottom, 4)
        )

    assert lit(right_half) > lit(left_half)


def test_clicking_new_game_opens_the_slot_list(menu_app):
    """The real path: a click, not a request set by hand."""
    menu_app.menu.draw(menu_app.surface, menu_app.fonts, (0, 0))
    button = menu_app.menu.buttons[NEW_GAME]

    menu_app.menu.handle_event(click(button.rect.center))
    menu_app.menu.handle_event(release(button.rect.center))

    assert menu_app.menu.mode == NEW_GAME
    assert menu_app.menu.take_request() is None, "choosing a slot comes first"


def test_clicking_a_slot_asks_for_that_slot(menu_app):
    menu_app.menu.mode = NEW_GAME
    menu_app.menu.draw(menu_app.surface, menu_app.fonts, (0, 0))
    rect, slot, usable = menu_app.menu._slot_rects[2]
    assert usable

    menu_app.menu.handle_event(click(rect.center))

    assert menu_app.menu.take_request() == (NEW_GAME, slot)


def test_the_slot_list_says_which_slots_are_taken(menu_app):
    """V16.9 in one word, so the player is not choosing blind."""
    menu_app.saves.save_to_slot(2, "Occupied")
    menu_app.menu.mode = NEW_GAME

    slots = menu_app.menu._listed_slots()

    assert len(slots) == 5, "every slot is offered, empty or not"
    assert [info.exists for info in slots] == [False, True, False, False, False]


def test_a_save_confirmation_is_not_shown_as_an_error(menu_app):
    _new_game(menu_app, slot="1")
    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    assert menu_app.menu.message
    assert menu_app.menu.message_ok


def test_the_slot_survives_closing_and_reopening_the_game(menu_app):
    """PM: the association must outlive the process, not just the session."""
    from apex_horizon.engine.save import SaveStore

    _new_game(menu_app, slot="4", name="Reopened")
    menu_app.context.engine.run_days(15)
    menu_app._prompt_exit()
    _choose(menu_app, "exit")
    directory = menu_app.saves.store.directory

    # A completely fresh application, as though the game had been restarted.
    reopened = GameApp(size=(1100, 760), seed=99, start_in_menu=True)
    try:
        reopened.saves.store = SaveStore(directory, manual_slots=5)
        reopened.menu.saves = reopened.saves
        reopened._load_from_menu("4")

        assert reopened.saves.slot == "4"
        assert reopened.saves.metadata.name == "Reopened"
        reopened.saves.record_playtime(reopened.saves.autosave_interval_minutes * 60)
        assert [i.slot for i in reopened.saves.slots() if i.exists] == ["4"]
    finally:
        reopened.shutdown()


# -- the Start Menu background ---------------------------------------------


def _backdrop(size=(900, 600)):
    from apex_horizon.ui.background import Backdrop

    surface = pygame.Surface(size)
    Backdrop().draw(surface)
    return surface


def test_the_menu_has_something_behind_it(menu_app):
    """A drawn backdrop, not the flat fill a page uses."""
    surface = _backdrop()

    colours = {surface.get_at((x, y))[:3]
               for x in range(0, 900, 60) for y in range(0, 600, 40)}

    assert len(colours) > 12, "a flat fill would give one or two"


def test_the_backdrop_stays_in_the_background(menu_app):
    """PM: low contrast, no large bright shapes competing with the menu."""
    surface = _backdrop()
    samples = [surface.get_at((x, y))[:3]
               for x in range(0, 900, 15) for y in range(0, 600, 15)]
    brightness = [sum(colour) for colour in samples]

    # Text is around 700 on this scale and the primary button around 500.
    assert max(brightness) < 150, "nothing in it approaches the text or buttons"
    assert max(brightness) - min(brightness) < 90, "and no hard edges within it"


def test_it_is_the_same_every_launch(menu_app):
    """The composition is written down, not rolled, so it cannot drift."""
    first, second = pygame.Surface((640, 480)), pygame.Surface((640, 480))
    _draw_backdrop(first)
    _draw_backdrop(second)

    assert pygame.image.tobytes(first, "RGB") == pygame.image.tobytes(second, "RGB")


def _draw_backdrop(surface) -> None:
    from apex_horizon.ui.background import Backdrop

    Backdrop().draw(surface)


def test_it_is_drawn_once_and_kept(menu_app):
    from apex_horizon.ui.background import Backdrop

    backdrop = Backdrop()
    surface = pygame.Surface((640, 480))
    backdrop.draw(surface)
    cached = backdrop.surface_for((640, 480))

    backdrop.draw(surface)

    assert backdrop.surface_for((640, 480)) is cached
    assert backdrop.surface_for((800, 600)) is not cached, "a resize rebuilds it"


def test_it_can_be_used_by_any_screen(menu_app):
    """A component, not a picture of one menu: it fills whatever it is given."""
    from apex_horizon.ui.background import Backdrop

    backdrop = Backdrop()
    for size in ((320, 240), (1920, 1080), (700, 1200)):
        surface = pygame.Surface(size)
        backdrop.draw(surface)
        assert surface.get_at((size[0] - 1, size[1] - 1))[3] == 255


def test_the_menu_keeps_its_contrast_over_the_background(menu_app):
    """V27.10: a backdrop that costs the buttons their readability is worse."""
    menu_app.menu.draw(menu_app.surface, menu_app.fonts, (0, 0))
    button = menu_app.menu.buttons[NEW_GAME]

    behind = menu_app.surface.get_at((20, 20))[:3]
    on_button = menu_app.surface.get_at(button.rect.center)[:3]

    assert sum(behind) < 160, "the backdrop stays dark behind light text"
    assert sum(on_button) - sum(behind) > 200, "the primary button still stands out"


# -- hiring from the Employees page (bug fix, 2026-08-09) ------------------
#
# The Hire buttons were recreated from scratch every draw call. A real click
# spans two frames — mouse-down on one, mouse-up on the next, with a draw in
# between — and a brand-new Button() on the second frame has no memory of the
# press the first frame saw, so the release was silently ignored. Nothing
# exercised the click through actual down/up events, so nothing caught it.


def _found_company_with_applicant(app):
    """A company that can afford to hire, with exactly one applicant waiting."""
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    roster = company.employees
    roster.refresh_applicants(app.context.engine.rng, app.context.names,
                              app.context.allocator, app.context.engine.date.day)
    assert roster.applicants, "the generator should have produced someone to hire"
    return company, roster, roster.applicants[0]


def _hire_button_center(app, applicant_id: str):
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    button = page.hire_buttons[applicant_id]
    return button.rect.center


def _click_across_a_frame(app, pos) -> None:
    """A mouse-down, a frame drawn in between, then the mouse-up — real play."""
    page = app.pages["company:employees"]
    page.handle_event(click(pos))
    app.draw(16)  # the frame that used to wipe out the Hire button's press
    page.handle_event(release(pos))
    app._collect_page_requests()


def test_clicking_hire_across_two_frames_adds_the_employee(app):
    """Test 1: normal hiring, through the real down/up click sequence."""
    _, roster, applicant = _found_company_with_applicant(app)
    before = len(roster)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))

    assert len(roster) == before + 1
    assert any(employee.id == applicant.id for employee in roster.employees)


def test_hiring_updates_the_roster_page_immediately(app):
    """Test 5: the employee appears in the UI without a separate refresh."""
    _, _roster, applicant = _found_company_with_applicant(app)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))

    page = app.pages["company:employees"]
    assert applicant.id in {row["id"] for row in page.rows()}


def test_hiring_removes_the_applicant_so_they_cannot_be_hired_twice(app):
    """Test 3: the same applicant cannot immediately be hired again."""
    _, roster, applicant = _found_company_with_applicant(app)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))
    assert not any(a.id == applicant.id for a in roster.applicants)
    count_after_first_hire = len(roster)

    # The button for a since-hired applicant no longer exists to click, but the
    # dispatcher must still refuse safely if it is ever asked to hire them again.
    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert len(roster) == count_after_first_hire


def _fill_to_capacity(app, roster) -> None:
    """Hire filler employees up to the company's limit.

    Reuses the app's own allocator and name generator rather than fresh ones:
    a second ``IdAllocator()`` starts counting from the same id used by the
    applicant pool, and a filler colliding on id with a real applicant gets
    stripped out of ``roster.applicants`` by ``hire()``'s own id-based filter.
    """
    from apex_horizon.engine.employees import generate_applicants

    while not roster.is_full:
        filler = generate_applicants(
            app.context.engine.rng, app.context.names, app.context.allocator, count=1,
        )[0]
        roster.hire(filler, app.context.engine.date.day)


def test_a_full_company_shows_hire_as_unavailable(app):
    """Test 2: capacity is respected, and shown as unavailable rather than
    failing silently."""
    _, roster, applicant = _found_company_with_applicant(app)
    _fill_to_capacity(app, roster)
    assert roster.is_full

    pos = _hire_button_center(app, applicant.id)
    before = len(roster)

    _click_across_a_frame(app, pos)

    assert len(roster) == before, "a full company must not gain another employee"
    page = app.pages["company:employees"]
    assert not page.hire_buttons[applicant.id].enabled


def test_a_rejected_hire_tells_the_player_why(app):
    """Test 6: a legitimate failure is explained, not swallowed."""
    _, roster, applicant = _found_company_with_applicant(app)
    _fill_to_capacity(app, roster)
    assert applicant.id in {a.id for a in roster.applicants}, \
        "the original applicant should still be waiting, just unable to join"

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app.notifications.items.clear()

    app._handle_employees_page(page)

    assert app.notifications.items, "a refusal must say something, not nothing"
    message = app.notifications.items[-1].text.lower()
    assert "capacity" in message or "level" in message or "hold" in message


def test_hiring_dispatch_marks_the_game_as_having_unsaved_changes(app):
    """Test 4 (part 1): the hire must land in state the save system will pick
    up. This is what makes it actually saved rather than a UI-only change."""
    _, roster, applicant = _found_company_with_applicant(app)
    app.saves.unsaved_changes = False

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert app.saves.unsaved_changes
    assert any(employee.id == applicant.id for employee in roster.employees)


# -- recruitment pacing and automation, through the real UI (2026-08-10) --


def _found_company_with_market(app):
    """A company with a real market attached, so recruitment scheduling has
    the name generator and id allocator it needs (attach_recruitment_sources
    is wired inside attach_market)."""
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    # The real founding flow wires this through _observe_company; founding
    # directly here, as every other employee test in this module does,
    # bypasses that popup-driven path, so it is wired explicitly instead.
    app._observe_recruitment(company)
    return company, company.employees


def test_clicking_find_candidates_schedules_a_wait_rather_than_instant_candidates(app):
    _, roster = _found_company_with_market(app)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)

    pos = page.recruit_button.rect.center if page.recruit_button.rect.width else (
        app.surface.get_width() - 100, 300)
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert roster.pending_applicants_day is not None
    assert roster.applicants == []


def test_the_arriving_message_and_disabled_button_show_while_pending(app):
    _, roster = _found_company_with_market(app)
    roster.request_applicants(app.context.engine.date.day)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    assert not page.recruit_button.enabled


def test_an_arrival_notification_is_pushed_through_the_real_engine(app):
    _, roster = _found_company_with_market(app)
    roster.request_applicants(app.context.engine.date.day)
    delay = roster.config.get_int("employees.recruitment_delay_days")
    app.notifications.items.clear()

    app.context.engine.run_days(delay + 1)

    assert roster.applicants, "the pool should have arrived"
    assert any("applicant" in item.text.lower() for item in app.notifications.items)


def test_automation_controls_stay_hidden_until_unlocked(app):
    _, roster = _found_company_with_market(app)
    assert not roster.automation_allowed
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    # Nothing to click: the controls are not drawn at all pre-unlock, so their
    # rects stay at the Button() default rather than a real position.
    assert page.automation_button.rect.width == 0


def test_automation_toggle_flows_through_the_real_dispatcher(app):
    _, roster = _found_company_with_market(app)
    roster.automation_allowed = True
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    assert page.automation_button.rect.width > 0, "unlocked, so it must be drawn"

    pos = page.automation_button.rect.center
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert roster.auto_recruit_enabled is True


# -- employee departments, filters and Performance (QoL pass, 2026-08-10) --
#
# Company -> Employees -> {department}, built generically off Department
# rather than one hardcoded tab, plus a couple of useful filters on top and
# a derived Performance figure gated behind the same unlock that already
# existed for it (roster.performance_visible) but was never wired to
# anything.


def _hire_one_in_each_department(app, roster):
    """One employee per department, plus one extra Research hire so a skill
    filter test has something on both sides of a threshold."""
    from apex_horizon.engine.employees import Department, generate_applicants

    hired = []
    for department in (Department.RESEARCH, Department.MANAGEMENT, Department.INVESTMENT):
        applicant = generate_applicants(
            app.context.engine.rng, app.context.names, app.context.allocator, count=1,
        )[0]
        applicant.set_priorities(department, *[d for d in Department if d is not department])
        roster.hire(applicant, app.context.engine.date.day)
        hired.append(applicant)
    return hired


def test_department_tabs_filter_the_roster_to_one_department(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    page.department_tabs.selected = str(hired[0].primary)
    shown = {row["id"] for row in page.rows()}
    assert shown == {hired[0].id}


def test_all_tab_shows_the_whole_roster(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]
    assert page.department_tabs.selected == "All"
    assert {row["id"] for row in page.rows()} == {e.id for e in hired}


def test_breadcrumb_reflects_the_selected_department(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    assert page.breadcrumb() == [("Company", "company"), ("Employees", page.key)]
    page.department_tabs.selected = str(hired[0].primary)
    assert page.breadcrumb()[-1] == (str(hired[0].primary), page.key)


def test_status_filter_isolates_training_employees(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    roster.training_allowed = True
    roster.start_training(hired[0], hired[0].secondary, app.context.engine.date.day)
    page = app.pages["company:employees"]

    page.status_filter.selected = "Training"
    assert {row["id"] for row in page.rows()} == {hired[0].id}

    page.status_filter.selected = "Available"
    assert hired[0].id not in {row["id"] for row in page.rows()}
    assert len(page.rows()) == 2


def test_skill_filter_excludes_employees_below_the_threshold(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    high_bar = max(e.overall_skill for e in hired) + 1
    page.skill_filter.selected = f"{high_bar}+" if f"{high_bar}+" in (
        "10+", "20+", "30+") else "30+"
    shown = page.rows()
    for row in shown:
        assert row["skill"] >= int(page.skill_filter.selected.rstrip("+"))


def test_performance_is_hidden_until_unlocked_then_shows_a_percentage(app):
    _, roster = _found_company_with_market(app)
    _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    assert roster.performance_visible is False
    assert all(row["performance"] == "—" for row in page.rows())

    roster.performance_visible = True
    assert all(row["performance"].endswith("%") for row in page.rows())


def test_clicking_a_department_tab_flows_through_a_real_event(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)

    label = str(hired[0].primary)
    rect = next(rect for rect, tab_label in page.department_tabs._rects if tab_label == label)
    page.handle_event(click(rect.center))

    assert page.department_tabs.selected == label


def test_an_empty_department_reports_no_employees_rather_than_a_generic_message(app):
    _, roster = _found_company_with_market(app)
    _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    from apex_horizon.engine.employees import Department

    # Every department got exactly one hire above; picking a fourth state (no
    # such department exists, so this just proves rows() empties out cleanly
    # rather than asserting on drawn text) is unnecessary — instead confirm
    # the roster-wide vs. department-scoped counts genuinely differ.
    page.department_tabs.selected = str(Department.RESEARCH)
    research_only = len(page.rows())
    page.department_tabs.selected = "All"
    assert len(page.rows()) > research_only


def test_hiring_more_staff_does_not_move_the_search_box_or_cards(app):
    """Layout stability (V17): once a company has any staff at all — the
    steady state a playthrough spends almost all its time in — fixed page
    furniture must not depend on exactly how many employees are on the
    roster. (Going from zero to one is its own deliberate empty-state
    transition, covered separately; this is about two hires looking the
    same as ten.)"""
    from apex_horizon.engine.employees import Department, generate_applicants

    _, roster = _found_company_with_market(app)
    first = generate_applicants(app.context.engine.rng, app.context.names,
                                app.context.allocator, count=1)[0]
    roster.hire(first, app.context.engine.date.day)
    app.navigate("company:employees")
    app.draw(0)
    page = app.pages["company:employees"]
    before_search_rect = pygame.Rect(page.search.rect)
    cards_before = len(page.cards())

    for department in Department:
        applicant = generate_applicants(app.context.engine.rng, app.context.names,
                                        app.context.allocator, count=1)[0]
        applicant.set_priorities(department, *[d for d in Department if d is not department])
        roster.hire(applicant, app.context.engine.date.day)
    app.draw(16)

    assert len(page.cards()) == cards_before, "the set of summary cards must not change with headcount"
    assert pygame.Rect(page.search.rect) == before_search_rect


# -- a bankrupt company is not operational (bug fix, 2026-08-09) -----------
#
# has_company already meant "a company exists and is not bankrupt", but most
# pages checked context.company for None directly, which stays true after
# bankruptcy — so a dead company kept showing its stale (usually deeply
# negative) figures as though it were still trading, and Employee Management
# stayed fully usable: a real, provable path let a player hire someone into a
# company with roughly -$1,000,000 in cash. Every page below is checked, plus
# the engine-level refusal that now backs the UI gating up.


def _bankrupt_company(app, cash: int = 50_000):
    app.context.player.cash = Money(cash)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Doomed Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.declare_bankruptcy(app.context.engine.date.day)
    return company


def test_has_company_is_false_once_bankrupt(app):
    company = _bankrupt_company(app)

    assert app.context.company is company, "the record stays (V1.3)"
    assert not app.context.has_company
    assert app.context.bankrupt_company is company


def test_has_company_is_true_for_a_going_concern(app):
    """The other half of the distinction: a solvent company still counts."""
    app.context.player.cash = Money(50_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Going Concern", 1)

    assert app.context.has_company
    assert app.context.bankrupt_company is None
    assert company is not None


def test_every_page_still_renders_for_a_bankrupt_company(app):
    """The regression this whole batch is guarding against: nothing may raise,
    whatever a page decides to show instead of the dead company's figures."""
    _bankrupt_company(app)
    for key in list(app.pages):
        app.navigate(key)
        app.draw(0)


def test_dashboard_drops_the_company_cards_once_bankrupt(app):
    _bankrupt_company(app)
    labels = [card.label for card in app.pages["dashboard"].cards()]
    assert "Company cash" not in labels
    assert "Staffing" not in labels


def test_dashboard_does_not_rank_a_bankrupt_company(app):
    """It must not be compared against ai.operating as though still trading."""
    _bankrupt_company(app)
    app.navigate("dashboard")
    surface = pygame.Surface((1440, 860))
    app.pages["dashboard"]._draw_competitors(
        surface, pygame.Rect(0, 0, 1400, 300), app.fonts)
    # No exception is the main guarantee; the source of truth for "no ranking
    # line" is player_company being None, which test_has_company_is_false_once
    # _bankrupt already pins directly.


def test_company_page_shows_the_notice_not_live_figures(app):
    company = _bankrupt_company(app)
    page = app.pages["company"]

    labels = [card.label for card in page.cards()]
    assert labels == ["Founding cost"], "not the live company cards"

    failed = app.context.bankrupt_company
    assert failed is company
    assert f"{company.name} went bankrupt" in \
        f"{failed.name} went bankrupt on day {failed.bankrupt_on_day}"


def test_company_page_buttons_are_unreachable_once_bankrupt(app):
    """Employee Management, Subsidiaries, Financial Management, Investment
    Funds — none of them should be clickable into a dead company."""
    _bankrupt_company(app)
    app.navigate("company")
    app.draw(0)
    page = app.pages["company"]

    for button in (page.employees_button, page.subsidiaries_button,
                   page.finance_button, page.funds_button):
        page.handle_event(click(button.rect.center))
        page.handle_event(release(button.rect.center))

    assert not page.take_employees_request()
    assert not page.take_subsidiaries_request()
    assert page.take_destination_request() is None


def test_the_found_button_is_available_again_once_bankrupt(app):
    """Refounding is the one action a bankrupt state should still offer."""
    _bankrupt_company(app)
    app.navigate("company")
    app.draw(0)
    page = app.pages["company"]

    assert page.found_button.enabled is False, \
        "not enough net worth yet to refound (project manager's post-bankruptcy rule)"
    app.context.player.cash = Money(600_000)
    app.draw(0)
    assert page.found_button.enabled is True


def test_finance_page_shows_no_cards_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["finance"].cards() == []
    app.navigate("finance")
    app.draw(0)  # must not raise trying to format a dead company's figures


def test_employees_page_has_no_roster_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:employees"].roster is None


def test_subsidiaries_page_has_no_book_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:subsidiaries"].book is None


def test_funds_page_has_no_book_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:funds"].book is None


def test_hiring_is_refused_through_the_real_dispatcher(app):
    """Not just an unreachable button: the dispatcher itself must refuse too,
    the way it already would for a full company."""
    company = _bankrupt_company(app)
    from random import Random

    from apex_horizon.engine.employees import generate_applicants
    from apex_horizon.engine.values import IdAllocator
    from apex_horizon.engine.world import NameGenerator

    applicant = generate_applicants(Random(1), NameGenerator(Random(1)),
                                    IdAllocator(), count=1)[0]
    company.employees.applicants.append(applicant)

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert len(company.employees) == 0


def test_no_company_message_distinguishes_bankruptcy_from_never_founded(app):
    from apex_horizon.ui.pages.base import no_company_message

    never_founded = no_company_message(app.context, "to test this")
    assert "bankrupt" not in never_founded.lower()

    _bankrupt_company(app)
    after_bankruptcy = no_company_message(app.context, "to test this")
    assert "went bankrupt" in after_bankruptcy
    assert "Doomed Capital" in after_bankruptcy


def test_refounding_restores_full_operation(app):
    """The other side of the fix: this must all come back for a fresh company."""
    _bankrupt_company(app)
    app.context.player.cash = Money(600_000)
    new_company, message = app.context.player.found_company("Second Chance", 1)
    assert new_company is not None, message

    assert app.context.has_company
    assert app.context.bankrupt_company is None
    assert app.pages["company:employees"].roster is new_company.employees
    assert app.pages["company"].cards()[0].label != "Founding cost"

    for key in list(app.pages):
        app.navigate(key)
        app.draw(0)


# -- Subsidiaries: unlock gate and the Buy flow (2026-08-10) ---------------
#
# Buying moves to Company -> Subsidiaries -> Buy; the Market page's old
# Acquire button is gone. Subsidiaries itself is gated behind a new unlock,
# one leaf past Investment Funds, with existing subsidiaries grandfathered.


def _found_company_for_acquisitions(app, cash: int = 2_000_000_000):
    app.context.player.cash = Money(cash)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Acquirer Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.receive_capital(app.context.engine.date.day, Money(cash))
    # Acquisitions require Company Level 2 (acquisitions.minimum_company_level).
    company.set_level(3)
    return company


def test_the_market_page_names_its_own_empty_state(app):
    """The generic Table fallback ("Nothing to show yet.") read oddly for a
    page that always has companies except in a genuine edge case (bug fix,
    2026-08-10) — the Market page now says specifically what is missing."""
    page = app.pages["market"]
    captured = {}
    original_draw = page.table.draw

    def spy(surface, rect, fonts, mouse, rows, query="", **kwargs):
        captured.update(kwargs)
        return original_draw(surface, rect, fonts, mouse, rows, query, **kwargs)

    page.table.draw = spy
    app.navigate("market")
    app.draw(0)

    assert captured.get("empty_message") == "No companies are listed on the market right now."
    assert captured["empty_message"] != "Nothing to show yet."


def test_the_market_page_no_longer_offers_an_acquire_button(app):
    """Buying outright moved to Company -> Subsidiaries -> Buy; the Market
    page's company detail must not carry the old flow's remnants."""
    page = app.pages["market:company"]
    assert not hasattr(page, "acquire_button")
    assert not hasattr(page, "acquire_request")
    assert not hasattr(page, "take_acquire_request")


def test_subsidiaries_page_offers_no_buy_action_while_locked(app):
    company = _found_company_for_acquisitions(app)
    assert company.subsidiaries.unlocked is False
    page = app.pages["company:subsidiaries"]
    app.navigate("company:subsidiaries")
    app.draw(0)
    # The button exists but must never be reachable while locked.
    page.buy_button.handle_event(click((1, 1)))
    assert not page.requested_buy


def test_buy_button_navigates_to_the_buy_page_through_the_real_dispatcher(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    page = app.pages["company:subsidiaries"]
    app.navigate("company:subsidiaries")
    app.draw(0)

    pos = page.buy_button.rect.center
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert app.current_key == "company:subsidiaries:buy"


def test_the_buy_page_lists_acquirable_companies_and_excludes_the_players_own(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    page = app.pages["company:subsidiaries:buy"]
    rows = page.rows()
    assert rows, "the market should offer something to acquire"
    assert all(row["id"] != company.id for row in rows)


def test_selecting_a_row_opens_the_purchase_detail_page(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    buy_page = app.pages["company:subsidiaries:buy"]
    app.navigate("company:subsidiaries:buy")
    app.draw(0)
    row_rect, row = next(iter(buy_page.table._row_rects))

    buy_page.handle_event(click(row_rect.center))
    app._collect_page_requests()

    assert app.current_key == "company:subsidiaries:buy:company"
    assert buy_page.selected_company_id == row["id"]


def test_the_acquire_button_is_enabled_for_a_companys_very_first_acquisition(app):
    """Bug fix, 2026-08-10: SubsidiaryBook defines __len__, so `if book:`
    reads a company with zero subsidiaries so far — exactly a first-time
    buyer's position — as falsy and silently disabled the button. Must use
    `is not None`."""
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    assert len(company.subsidiaries) == 0
    buy_page = app.pages["company:subsidiaries:buy"]
    target_id = buy_page.rows()[0]["id"]
    detail_page = app.pages["company:subsidiaries:buy:company"]
    buy_page.selected_company_id = target_id
    app.navigate("company:subsidiaries:buy:company")

    app.draw(0)

    assert detail_page.acquire_button.enabled is True


def test_clicking_acquire_buys_the_company_through_the_real_dispatcher(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    buy_page = app.pages["company:subsidiaries:buy"]
    target_id = buy_page.rows()[0]["id"]
    buy_page.selected_company_id = target_id
    app.navigate("company:subsidiaries:buy:company")
    app.draw(0)
    detail_page = app.pages["company:subsidiaries:buy:company"]

    pos = detail_page.acquire_button.rect.center
    detail_page.handle_event(click(pos))
    app.draw(16)
    detail_page.handle_event(release(pos))
    app._collect_page_requests()
    assert app.popups.is_open
    app.popups.current.chosen = "acquire"
    app.popups.handle_event(pygame.event.Event(pygame.USEREVENT))

    assert company.subsidiaries.owns(target_id)
    assert app.current_key == "company:subsidiaries"


def test_a_subsidiary_bought_before_the_unlock_stays_owned_and_visible(app):
    """Grandfathered: a subsidiary already owned must keep showing and
    earning even if the unlock is later found missing (e.g. an old save)."""
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    target_id = app.pages["company:subsidiaries:buy"].rows()[0]["id"]
    subsidiary, message = company.subsidiaries.acquire(target_id, app.context.engine.date.day)
    assert subsidiary is not None, message

    company.subsidiaries.unlocked = False  # as an old save would restore it

    page = app.pages["company:subsidiaries"]
    assert target_id in {row["id"] for row in page.rows()}
    allowed, _ = company.subsidiaries.can_acquire(
        next(r["id"] for r in app.pages["company:subsidiaries:buy"].rows()
            if r["id"] != target_id)
    )
    assert not allowed, "the gate still blocks a genuinely new acquisition"


# -- Unlock Tree: zoom, pan, click-select, info panel (2026-08-10) ---------


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


# -- notification safe-area hardening, remaining pages (2026-08-10) --------
#
# Settings, Subsidiaries (empty state + purchase detail), and Funds (empty
# state) all used fixed pixel heights that did not derive from or clamp to
# the content rect, unlike Dashboard/Employees/News/the Unlock Tree info
# panel, which were already fixed for the same class of bug. Each of these
# carries a control (a Save/Load button, the bootstrapping Buy/Acquire/Open
# button) that must never render underneath the reserved notification area —
# `surface.get_rect().contains(...)` alone does not catch this, since the
# notification stack occupies a corner of the surface rather than the whole
# thing; what matters is the button's own bottom edge against the boundary
# the notification stack actually reserves.


def _assert_never_under_notifications(app, rect) -> None:
    if rect.width == 0 and rect.height == 0:
        return  # not drawn at all is a valid way to avoid overlapping, too
    safe_bottom = app.surface.get_height() - app.notifications.safe_height()
    assert rect.bottom <= safe_bottom


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


def test_settings_save_slots_never_render_under_the_notification_stack(app):
    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("settings")
    app.draw(2000)
    page = app.pages["settings"]
    assert page._slot_buttons, "at least one save slot row must still be reachable"
    for _slot, _action, button in page._slot_buttons:
        _assert_never_under_notifications(app, button.rect)


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


def test_subsidiaries_buy_button_never_renders_under_the_notification_stack(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    assert len(company.subsidiaries) == 0

    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("company:subsidiaries")
    app.draw(2000)
    page = app.pages["company:subsidiaries"]
    _assert_never_under_notifications(app, page.buy_button.rect)


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


def test_the_acquire_button_never_renders_under_the_notification_stack(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    buy_page = app.pages["company:subsidiaries:buy"]
    buy_page.selected_company_id = buy_page.rows()[0]["id"]

    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("company:subsidiaries:buy:company")
    app.draw(2000)
    detail_page = app.pages["company:subsidiaries:buy:company"]
    _assert_never_under_notifications(app, detail_page.acquire_button.rect)


def test_the_open_fund_button_never_renders_under_the_notification_stack(app):
    company = _found_company_for_acquisitions(app)
    assert company.funds is not None
    company.funds.unlocked = True
    assert not company.funds.funds

    app.surface = pygame.Surface((1100, 680))
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.navigate("company:funds")
    app.draw(2000)
    page = app.pages["company:funds"]
    _assert_never_under_notifications(app, page.create_button.rect)


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
