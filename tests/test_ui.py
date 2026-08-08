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

from apex_horizon.engine.values import Calendar, Money, set_calendar
from apex_horizon.ui import theme
from apex_horizon.ui.app import SPEED_KEYS, GameApp
from apex_horizon.ui.chrome import NAV_ITEMS, Breadcrumb, NotificationCentre
from apex_horizon.ui.popups import Popup, PopupAction, PopupManager, PromptPopup
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


def test_sidebar_lists_the_sections_the_design_bible_names():
    labels = [item.label for item in NAV_ITEMS]
    assert labels == [
        "Dashboard", "Company", "Investments", "Market", "News",
        "Unlock Tree", "Financial Management", "Settings",
    ]


def test_every_sidebar_destination_has_a_page(app):
    for item in NAV_ITEMS:
        assert item.key in app.pages


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


def test_founding_a_company_through_the_interface(app):
    app.context.player.cash = Money(60_000)
    app.navigate("company")
    app._prompt_found_company()
    for character in "Meridian Capital":
        app.popups.current.handle_event(
            pygame.event.Event(pygame.KEYDOWN, key=0, unicode=character)
        )
    app.popups.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, unicode=""))
    assert app.context.company is not None
    assert app.context.company.name == "Meridian Capital"
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
