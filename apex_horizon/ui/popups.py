"""Modal decisions.

Design Bible V14.15 reserves popups for decisions important enough to justify
interrupting play — confirmations, major acquisitions, critical financial
choices. Every popup pauses the simulation (V13.20), so the player never loses
money or misses an opportunity while deciding, which matters most where a
changing market could move underneath them.

V27.6 sets the shape: a clear default action, a clear way to cancel, and never
more than one decision in a single popup. Because the pause is the cost of
opening one, a popup that does not deserve that pause should be a notification
instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import pygame

from . import theme
from .widgets import Button, draw_text, panel


@dataclass
class PopupAction:
    """One choice a popup offers."""

    key: str
    label: str
    primary: bool = False


@dataclass
class Popup:
    """A single decision put to the player."""

    title: str
    message: str
    actions: list[PopupAction] = field(default_factory=list)
    # Set when the player chooses; read and cleared by the application.
    chosen: str | None = None
    dismissible: bool = True
    _buttons: dict[str, Button] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not self.actions:
            self.actions = [PopupAction("ok", "OK", primary=True)]
        for action in self.actions:
            self._buttons[action.key] = Button(action.label, primary=action.primary)

    @property
    def cancel_key(self) -> str | None:
        """The action treated as cancelling, used by Escape (V27.6, V27.9)."""
        for action in self.actions:
            if not action.primary:
                return action.key
        return self.actions[0].key if len(self.actions) == 1 else None

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE and self.dismissible and self.cancel_key:
                self.chosen = self.cancel_key
                return True
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                primary = next((a for a in self.actions if a.primary), None)
                if primary:
                    self.chosen = primary.key
                    return True
        for key, button in self._buttons.items():
            if button.handle_event(event) and button.take_click():
                self.chosen = key
                return True
        # A modal swallows every click, so nothing behind it can be operated.
        return event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)

    def draw(self, surface, fonts, mouse) -> None:
        screen = surface.get_rect()
        veil = pygame.Surface(screen.size, pygame.SRCALPHA)
        veil.fill((*theme.OVERLAY, 200))
        surface.blit(veil, (0, 0))

        width, height = 460, 210
        rect = pygame.Rect(0, 0, width, height)
        rect.center = screen.center
        panel(surface, rect, fill=theme.SURFACE_RAISED, border=theme.BORDER_STRONG)

        draw_text(surface, fonts.heading, self.title, (rect.left + 28, rect.top + 26))
        _draw_wrapped(surface, fonts.body, self.message,
                      pygame.Rect(rect.left + 28, rect.top + 68, rect.width - 56, 80),
                      theme.TEXT_MUTED)

        x = rect.right - 28
        for action in reversed(self.actions):
            button = self._buttons[action.key]
            button_rect = pygame.Rect(0, 0, 116, 36)
            button_rect.topright = (x, rect.bottom - 56)
            button.draw(surface, button_rect, fonts, mouse)
            x -= button_rect.width + 10


class PopupManager:
    """Holds the one popup that may be open at a time.

    Only one decision is ever put to the player at once (V27.6). Requests that
    arrive while a popup is open are queued rather than stacked on top of it.
    """

    def __init__(self) -> None:
        self.current: Popup | None = None
        self._queue: list[Popup] = []
        self._handlers: dict[int, Callable[[str], None]] = {}

    @property
    def is_open(self) -> bool:
        """True while the simulation should be paused (V13.20)."""
        return self.current is not None

    def open(self, popup: Popup, on_choice: Callable[[str], None] | None = None) -> None:
        if on_choice is not None:
            self._handlers[id(popup)] = on_choice
        if self.current is None:
            self.current = popup
        else:
            self._queue.append(popup)

    def handle_event(self, event) -> bool:
        if self.current is None:
            return False
        handled = self.current.handle_event(event)
        if self.current.chosen is not None:
            popup, self.current = self.current, None
            handler = self._handlers.pop(id(popup), None)
            if handler is not None and popup.chosen is not None:
                handler(popup.chosen)
            if self._queue:
                self.current = self._queue.pop(0)
        return handled

    def draw(self, surface, fonts, mouse) -> None:
        if self.current is not None:
            self.current.draw(surface, fonts, mouse)


def _draw_wrapped(surface, font, text: str, rect: pygame.Rect, colour) -> None:
    words = str(text).split()
    line, y = "", rect.top
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width or not line:
            line = candidate
            continue
        draw_text(surface, font, line, (rect.left, y), colour)
        y += font.get_height() + 4
        line = word
        if y > rect.bottom - font.get_height():
            break
    if line:
        draw_text(surface, font, line, (rect.left, y), colour)


@dataclass
class PromptPopup(Popup):
    """A popup that asks the player to type something.

    Used where the Design Bible requires the player to name something they own —
    their company (V3.3) or an investment fund (V11.6). The confirming action
    stays disabled until there is something to confirm, so the popup can never
    be completed into an invalid state.
    """

    placeholder: str = ""
    text: str = ""
    max_length: int = 40

    def handle_event(self, event) -> bool:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                return True
            typing = (
                event.key not in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE)
                and event.unicode and event.unicode.isprintable()
            )
            if typing:
                if len(self.text) < self.max_length:
                    self.text += event.unicode
                return True
        primary = next((a for a in self.actions if a.primary), None)
        if primary is not None:
            self._buttons[primary.key].enabled = bool(self.text.strip())
            if not self.text.strip() and event.type == pygame.KEYDOWN and event.key in (
                pygame.K_RETURN, pygame.K_KP_ENTER
            ):
                return True
        return super().handle_event(event)

    def draw(self, surface, fonts, mouse) -> None:
        super().draw(surface, fonts, mouse)
        screen = surface.get_rect()
        rect = pygame.Rect(0, 0, 460, 210)
        rect.center = screen.center
        field = pygame.Rect(rect.left + 28, rect.top + 106, rect.width - 56, 34)
        panel(surface, field, fill=theme.SURFACE, border=theme.ACCENT)
        shown = self.text or self.placeholder
        colour = theme.TEXT if self.text else theme.TEXT_FAINT
        draw_text(surface, fonts.body, shown, (field.left + 12, field.centery), colour,
                  baseline="middle")
        if self.text:
            caret_x = field.left + 12 + fonts.body.size(self.text)[0] + 2
            pygame.draw.line(surface, theme.TEXT_MUTED,
                             (caret_x, field.top + 8), (caret_x, field.bottom - 8))
