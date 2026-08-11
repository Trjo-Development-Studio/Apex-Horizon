"""Tables, popups, time controls, and the notification-safe content area."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import click

from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money
from apex_horizon.ui import theme
from apex_horizon.ui.app import SPEED_KEYS
from apex_horizon.ui.chrome import (
    NotificationCentre,
)
from apex_horizon.ui.popups import Popup, PopupAction, PopupManager, PromptPopup
from apex_horizon.ui.widgets import Column, SearchBox, Table, truncate

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


# -- notifications are a floating overlay (PM ruling, 2026-08-11) ---------
#
# They are drawn after the page and take no part in its layout. An earlier
# build reserved the lower-right corner out of every page's content rect so
# that a message could never cover a control; the project manager reversed
# that, because reserving space made the interface jump every time a message
# arrived or expired. Messages now float over whatever is there and leave it
# exactly as it was.


def test_notifications_reserve_no_space_at_all(app):
    """The heart of the ruling: the rect a page is laid out in must be the
    same whether or not anything is showing, and must reach the full height
    of the window either way."""
    seen = []
    page = app.pages["dashboard"]
    original = page.draw

    def record(surface, rect, fonts, mouse, breadcrumb):
        seen.append(pygame.Rect(rect))
        return original(surface, rect, fonts, mouse, breadcrumb)

    app.surface = pygame.Surface((1280, 800))
    app.navigate("dashboard")
    page.draw = record
    app.draw(2000)
    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.draw(2000)

    assert len(seen) == 2
    assert seen[0] == seen[1], "the page must be laid out identically either way"
    assert seen[0].bottom >= 800 - theme.PAGE_PADDING, "and reach the window's own bottom"


def test_nothing_underneath_a_notification_moves(app):
    """The same thing proved in pixels, across everything left of the stack:
    drawing with a full stack must leave every pixel the stack does not
    itself cover exactly as it was without one."""
    app.surface = pygame.Surface((1280, 800))
    app.navigate("company:employees")
    app.draw(2000)
    untouched = pygame.Rect(
        0, 0, 1280 - theme.NOTIFICATION_WIDTH - NotificationCentre.MARGIN, 800)
    before = pygame.image.tobytes(app.surface.subsurface(untouched), "RGB")

    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.draw(2000)
    after = pygame.image.tobytes(app.surface.subsurface(untouched), "RGB")

    assert after == before, "a notification moved something underneath it"


def test_a_short_window_still_shows_the_staff_table(app):
    """At the minimum window size the roster must be visible — it is no
    longer competing with a reservation for the room."""
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
    app.navigate("company:employees")
    app.draw(0)
    table = app.pages["company:employees"].table
    assert table._row_rects, "the staff table should have room to show a row"


def test_a_full_stack_leaves_the_hire_buttons_exactly_where_they_were(app):
    """Hire buttons were what the old reservation existed to protect. Under
    an overlay they simply never move: a message may float over one, but the
    button stays where the player last saw it."""
    app.context.player.cash = Money(500_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.employees.refresh_applicants(app.context.engine.rng, app.context.names,
                                         app.context.allocator, app.context.engine.date.day)

    app.surface = pygame.Surface((1100, 680))
    app.navigate("company:employees")
    app.draw(2000)
    page = app.pages["company:employees"]
    assert page.hire_buttons
    before = {key: pygame.Rect(button.rect) for key, button in page.hire_buttons.items()}

    for index in range(6):
        app.notifications.push(f"Message {index}", 0)
    app.draw(2000)

    after = {key: pygame.Rect(button.rect) for key, button in page.hire_buttons.items()}
    assert after == before


def test_a_staff_table_with_no_room_says_so_rather_than_leaving_a_gap(app):
    """Bug fix, 2026-08-09: table_height could land at exactly 0 — not
    negative, so `table_height > 0` never fired either — leaving a bare gap
    above the Candidates panel with nothing drawn to say why. Notifications
    no longer create this regime, so the page is measured directly at a
    height too short for both panels, which is the case the guard is for."""
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

    app.navigate("company:employees")
    page = app.pages["company:employees"]
    surface = pygame.Surface((900, 400))
    page.draw_content(surface, pygame.Rect(0, 0, 900, 200), app.fonts, (0, 0))

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
