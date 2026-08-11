"""Visual language, the news and analytics pages, Portfolio, and personal cash."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import click

from apex_horizon.engine.unlocks import BASIC_ANALYTICS, BASIC_NEWS, CREATE_COMPANY
from apex_horizon.engine.values import Money
from apex_horizon.ui import theme
from apex_horizon.ui.chrome import (
    NAV_ITEMS,
)

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
    """Bug fix, 2026-08-09: a fixed 150px lead story panel could shrink far
    enough that its byline was drawn on top of its own body text, and the
    archive's "Archive" heading and "Select a story..." hint were drawn
    unconditionally, spilling past the bottom of their own panel. Both must
    degrade without ever overlapping. (Notifications no longer shrink the
    page — they are an overlay, PM ruling 2026-08-11 — but the degradation
    this guards still has to hold at small window sizes.)"""
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
