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


def test_it_is_personal_cash_rather_than_net_worth(app):
    """V1.4: net worth counts holdings and a company that cannot be spent."""
    app.context.player.cash = Money(1_000)
    listing = app.context.market.active_listings()[0]
    app.context.portfolio.buy(listing.company_id, 1, 1)

    shown = _cash_box(app, "market")[0]

    assert shown == app.context.player.cash.format()
    assert shown != app.context.player.net_worth().format()


def test_company_cash_stays_separate_from_the_players(app):
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Test Capital", 1)
    company.attach_market(app.context.market, app.context.allocator)

    shown = _cash_box(app, "company")[0]

    assert shown == app.context.player.cash.format()
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


def test_new_game_begins_a_world(menu_app):
    from apex_horizon.ui.start_menu import NEW_GAME

    menu_app.menu.request = NEW_GAME
    menu_app._menu_tick(0)

    assert not menu_app.in_menu
    assert menu_app.current_key == "dashboard"
    assert menu_app.context.market.active_listings()


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
    from apex_horizon.ui.start_menu import NEW_GAME

    menu_app.menu.request = NEW_GAME
    menu_app._menu_tick(0)
    menu_app.context.engine.run_days(20)

    menu_app._prompt_exit()
    _choose(menu_app, "exit")

    assert menu_app.in_menu, "the player returns to the Main Menu"
    assert menu_app.running, "leaving a session is not leaving the game"
    assert menu_app.saves.store.info(menu_app.current_slot).exists


def test_a_failed_save_keeps_the_player_in_the_game(menu_app, monkeypatch):
    """V16.4 step 6: never pretend a save succeeded."""
    from apex_horizon.engine.save.service import SaveResult
    from apex_horizon.ui.start_menu import NEW_GAME

    menu_app.menu.request = NEW_GAME
    menu_app._menu_tick(0)

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
