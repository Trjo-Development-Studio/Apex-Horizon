"""The real logo, the window icon, and the Start Menu backdrop."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import _choose, _new_game, click, release

from apex_horizon.engine.values import Calendar, set_calendar
from apex_horizon.ui import theme
from apex_horizon.ui.app import GameApp
from apex_horizon.ui.chrome import (
    NAV_ITEMS,
)
from apex_horizon.ui.start_menu import NEW_GAME

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
    """Whichever way the player set it, navigating must not reset it — so
    this asserts the state it was toggled *to*, rather than assuming which
    way the toggle went from the default."""
    app.draw(0)
    app.sidebar.handle_event(click(app.sidebar._logo_rect.center))
    chosen = app.sidebar.expanded

    for item in NAV_ITEMS:
        app.navigate(item.key)
        app.draw(0)
        assert app.sidebar.expanded is chosen, item.label


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
