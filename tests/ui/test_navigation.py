"""Launching, sidebar navigation, and mouse back/forward through history."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import _choose, _new_game, click

from apex_horizon.ui.chrome import (
    FOOT_ITEMS,
    NAV_ITEMS,
    Breadcrumb,
)

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
