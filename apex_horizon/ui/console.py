"""The in-game developer console, opened with Ctrl+T.

V15.18 puts developer commands in the launching terminal, which works but is
only available to whoever started the game from one — not to a packaged build,
and not on a second monitor's worth of Windows shortcut. The project manager
asked for the same commands inside the window, so this is that surface: it owns
no commands of its own and knows nothing about money, time or unlocks. It reads
keys, and hands whole lines to :class:`~apex_horizon.debug.commands.DeveloperCommands`,
which is the same object the terminal drives. One language, two ways in.

It is styled as part of the game rather than as a terminal emulator (V1.15,
V14.20): the game's own palette and panels, a labelled header, commands in the
accent colour and refusals in red, so what was typed never reads as what the
game answered. Nothing here executes anything from the operating system.

While it is open the simulation is held still, exactly as a popup holds it
(V13.20) — a developer reading the world's state should not have it moving
underneath them.
"""

from __future__ import annotations

import pygame

from . import theme
from .widgets import draw_text, panel

#: How a line got into the log, which is the only thing its colour depends on.
COMMAND = "command"
OUTPUT = "output"
ERROR = "error"
SYSTEM = "system"

COLOURS = {
    COMMAND: theme.ACCENT,
    OUTPUT: theme.TEXT,
    ERROR: theme.NEGATIVE,
    SYSTEM: theme.TEXT_MUTED,
}

MAX_LINES = 400
MAX_INPUT = 120
LINE_HEIGHT = 18
PADDING = 18
HEADER_HEIGHT = 44
INPUT_HEIGHT = 38

WELCOME = (
    "Apex Horizon developer console. Type 'help' for the commands, "
    "Ctrl+T or Esc to close."
)


def opens_console(event) -> bool:
    """True for the Ctrl+T that opens and closes the console."""
    return (
        event.type == pygame.KEYDOWN
        and event.key == pygame.K_t
        and bool(event.mod & pygame.KMOD_CTRL)
    )


class ConsoleOverlay:
    """The console window: input, scrollback, and nothing else."""

    def __init__(self, commands):
        self.commands = commands
        self.open = False
        self.text = ""
        #: ``(text, kind)`` in the order they happened, oldest first.
        self.lines: list[tuple[str, str]] = [(WELCOME, SYSTEM)]
        self.history: list[str] = []
        self._history_index: int | None = None
        self._scroll = 0  # Lines scrolled up from the bottom.
        self._draft = ""
        self._rect = pygame.Rect(0, 0, 0, 0)
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        commands.on_output.append(self._on_late_output)

    # -- opening and closing -----------------------------------------------
    def toggle(self) -> None:
        self.hide() if self.open else self.show()

    def show(self) -> None:
        self.open = True
        self._scroll = 0
        # Holding a key down should repeat while typing, and nowhere else.
        pygame.key.set_repeat(350, 35)

    def hide(self) -> None:
        self.open = False
        pygame.key.set_repeat()

    # -- the log -----------------------------------------------------------
    def write(self, text: str, kind: str = OUTPUT) -> None:
        """Add output, one entry per line so long answers scroll properly."""
        for line in str(text).split("\n"):
            self.lines.append((line, kind))
        del self.lines[:-MAX_LINES]
        self._scroll = 0  # New output brings the view back to the newest line.

    def _on_late_output(self, message: str) -> None:
        """Something finished after its command returned — a time jump ending."""
        self.write(message, SYSTEM)

    def run(self, line: str) -> None:
        """Echo a command, run it, and record what it said."""
        self.write(f"> {line}", COMMAND)
        self.history.append(line)
        del self.history[:-MAX_LINES]
        reply = self.commands.execute(line)
        if reply:
            self.write(reply, OUTPUT if getattr(reply, "ok", True) else ERROR)

    # -- input -------------------------------------------------------------
    def handle_event(self, event) -> bool:
        """Consume every event while open, so nothing reaches the game behind."""
        if not self.open:
            return False
        if event.type == pygame.MOUSEWHEEL:
            self._scroll = max(0, min(self._scroll + event.y, len(self.lines) - 1))
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect.collidepoint(event.pos):
                self.hide()
            return True
        if event.type != pygame.KEYDOWN:
            return event.type == pygame.MOUSEBUTTONUP

        if opens_console(event) or event.key == pygame.K_ESCAPE:
            self.hide()
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            line, self.text = self.text.strip(), ""
            self._history_index = None
            if line:
                self.run(line)
            return True
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
            return True
        if event.key == pygame.K_TAB:
            self._complete()
            return True
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            self._recall(-1 if event.key == pygame.K_UP else 1)
            return True
        if event.key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            step = 8 if event.key == pygame.K_PAGEUP else -8
            self._scroll = max(0, min(self._scroll + step, len(self.lines) - 1))
            return True
        # Ctrl and Alt combinations are shortcuts, not text.
        if event.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
            return True
        if event.unicode and event.unicode.isprintable() and len(self.text) < MAX_INPUT:
            self.text += event.unicode
        return True

    def _complete(self) -> None:
        """Finish a command name, which is the only word the console knows."""
        if " " in self.text.strip() or not self.text.strip():
            return
        typed = self.text.strip().lower()
        matches = sorted(name for name in self.commands.commands if name.startswith(typed))
        if not matches:
            return
        if len(matches) == 1:
            self.text = matches[0] + " "
            return
        self.write("  ".join(matches), SYSTEM)

    def _recall(self, direction: int) -> None:
        """Walk back through what has been typed, as any console does."""
        if not self.history:
            return
        if self._history_index is None:
            if direction > 0:
                return
            self._draft = self.text
            self._history_index = len(self.history)
        index = self._history_index + direction
        if index >= len(self.history):
            self._history_index = None
            self.text = self._draft
            return
        self._history_index = max(0, index)
        self.text = self.history[self._history_index]

    # -- drawing -----------------------------------------------------------
    def draw(self, surface, fonts, now_ms: int) -> None:
        if not self.open:
            return
        screen = surface.get_rect()
        veil = pygame.Surface(screen.size, pygame.SRCALPHA)
        veil.fill((*theme.OVERLAY, 150))
        surface.blit(veil, (0, 0))

        width = min(960, screen.width - 80)
        height = min(560, screen.height - 80)
        rect = pygame.Rect(0, 0, width, height)
        rect.midtop = (screen.centerx, 40)
        self._rect = rect
        panel(surface, rect, fill=theme.SURFACE, border=theme.BORDER_STRONG)

        self._draw_header(surface, fonts, rect)
        log = pygame.Rect(rect.left + 10, rect.top + HEADER_HEIGHT + 8,
                          rect.width - 20,
                          rect.height - HEADER_HEIGHT - INPUT_HEIGHT - 32)
        pygame.draw.rect(surface, theme.BACKGROUND, log, border_radius=theme.CORNER)
        self._draw_lines(surface, fonts, log.inflate(-24, -20))
        self._draw_input(surface, fonts, rect, now_ms)

    def _draw_header(self, surface, fonts, rect) -> None:
        header = pygame.Rect(rect.left, rect.top, rect.width, HEADER_HEIGHT)
        pygame.draw.rect(surface, theme.SURFACE_RAISED, header,
                         border_top_left_radius=theme.CORNER,
                         border_top_right_radius=theme.CORNER)
        pygame.draw.line(surface, theme.ACCENT, (header.left, header.bottom - 1),
                         (header.right, header.bottom - 1))

        badge = pygame.Rect(header.left + PADDING, header.centery - 9, 34, 18)
        pygame.draw.rect(surface, theme.ACCENT_MUTED, badge, border_radius=3)
        draw_text(surface, fonts.tiny, "DEV", badge.center, theme.TEXT,
                  align="center", baseline="middle")
        draw_text(surface, fonts.subheading, "Developer Console",
                  (badge.right + 12, header.centery), theme.TEXT, baseline="middle")

        if self.commands.busy:
            draw_text(surface, fonts.small,
                      f"Simulating — {self.commands.pending_days:,} days left",
                      (header.centerx + 60, header.centery), theme.WARNING,
                      align="center", baseline="middle")

        self._close_rect = pygame.Rect(header.right - PADDING - 22,
                                       header.centery - 11, 22, 22)
        hovered = self._close_rect.collidepoint(pygame.mouse.get_pos())
        cross = self._close_rect.inflate(-9, -9)
        colour = theme.TEXT if hovered else theme.TEXT_MUTED
        pygame.draw.line(surface, colour, cross.topleft, cross.bottomright, 2)
        pygame.draw.line(surface, colour, cross.bottomleft, cross.topright, 2)
        draw_text(surface, fonts.tiny, "CTRL+T / ESC",
                  (self._close_rect.left - 10, header.centery), theme.TEXT_FAINT,
                  align="right", baseline="middle")

    def _draw_lines(self, surface, fonts, body) -> None:
        font = fonts.mono_small
        wrapped: list[tuple[str, str]] = []
        for text, kind in self.lines:
            wrapped += [(part, kind) for part in _wrap(font, text, body.width)]

        visible = max(1, body.height // LINE_HEIGHT)
        self._scroll = max(0, min(self._scroll, max(0, len(wrapped) - visible)))
        end = len(wrapped) - self._scroll
        shown = wrapped[max(0, end - visible):end]

        y = body.top
        for text, kind in shown:
            draw_text(surface, font, text, (body.left, y), COLOURS[kind])
            y += LINE_HEIGHT

        if len(wrapped) > visible:
            self._draw_scrollbar(surface, body, len(wrapped), visible, end)

    def _draw_scrollbar(self, surface, body, total, visible, end) -> None:
        track = pygame.Rect(body.right + 4, body.top, 3, body.height)
        pygame.draw.rect(surface, theme.BORDER, track, border_radius=2)
        height = max(24, int(track.height * visible / total))
        top = track.top + int((track.height - height) * (end - visible) / (total - visible))
        pygame.draw.rect(surface, theme.BORDER_STRONG,
                         pygame.Rect(track.left, top, track.width, height),
                         border_radius=2)

    def _draw_input(self, surface, fonts, rect, now_ms: int) -> None:
        field = pygame.Rect(rect.left + PADDING, rect.bottom - INPUT_HEIGHT - 12,
                            rect.width - PADDING * 2, INPUT_HEIGHT)
        panel(surface, field, fill=theme.BACKGROUND, border=theme.ACCENT_MUTED)
        draw_text(surface, fonts.mono_small, ">", (field.left + 12, field.centery),
                  theme.ACCENT, baseline="middle")
        left = field.left + 28
        draw_text(surface, fonts.mono_small, self.text, (left, field.centery),
                  theme.TEXT, baseline="middle")
        if now_ms % 1100 < 600:  # a caret that blinks rather than a solid block
            caret = left + fonts.mono_small.size(self.text)[0] + 1
            pygame.draw.rect(surface, theme.ACCENT,
                             pygame.Rect(caret, field.centery - 8, 7, 16))


def _wrap(font, text: str, width: int) -> list[str]:
    """Break one logged line into as many as it needs, keeping its indent."""
    if not text:
        return [""]
    if font.size(text)[0] <= width:
        return [text]
    indent = " " * (len(text) - len(text.lstrip()) + 2)
    lines: list[str] = []
    current = ""
    for word in text.split(" "):
        candidate = f"{current} {word}" if current else word
        if current and font.size(candidate)[0] > width:
            lines.append(current)
            current = indent + word
        else:
            current = candidate
    lines.append(current)
    return lines
