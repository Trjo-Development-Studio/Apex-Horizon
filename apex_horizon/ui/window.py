"""Application shell — window creation and the outer frame loop.

This is deliberately minimal. The complete User Interface System (Design Bible
V14 and V27) — sidebar, breadcrumbs, cards, lists, popups and notifications —
is a later milestone; the shell exists now so that every milestone can satisfy
the mandatory "the game launches successfully" test in V15.19 and V19.10.

TODO (Milestone: UI framework): replace the placeholder frame with the real
navigation shell, and drive rendering from the simulation engine once the Time &
Simulation System (V13) exists.
"""

from __future__ import annotations

import pygame

from .. import __version__
from ..engine.errors import subscribe_error_notifier
from ..engine.logging_setup import get_logger

logger = get_logger(__name__)

WINDOW_TITLE = "Apex Horizon"
# Placeholder window size; the real design canvas is defined with the UI system.
WINDOW_SIZE = (1280, 720)
TARGET_FPS = 60

# Neutral, professional placeholder palette (V1.15: clean, modern, minimalistic).
BACKGROUND = (18, 20, 24)
TEXT = (232, 235, 240)
MUTED = (138, 146, 158)


class GameWindow:
    """Creates the window and runs the outer frame loop."""

    def __init__(self, size: tuple[int, int] = WINDOW_SIZE):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.surface = pygame.display.set_mode(size)
        self.clock = pygame.time.Clock()
        self.running = True
        self.messages: list[str] = []
        # Surface engine errors to the player rather than failing silently (V15.13).
        subscribe_error_notifier(self._on_error)

    def _on_error(self, message: str) -> None:
        """Display an engine error message. Replaced by the real notification
        system (V14.16) once the UI framework exists."""
        self.messages.append(message)

    def handle_events(self) -> None:
        for event in pygame.event.get():
            closing = event.type == pygame.QUIT or (
                event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE
            )
            if closing:
                self.running = False

    def draw(self) -> None:
        self.surface.fill(BACKGROUND)
        font = pygame.font.SysFont(None, 48)
        small = pygame.font.SysFont(None, 24)
        title = font.render(f"{WINDOW_TITLE} {__version__}", True, TEXT)
        subtitle = small.render(
            "Foundation milestone — engine, configuration, logging.", True, MUTED
        )
        hint = small.render("Press Esc to exit.", True, MUTED)
        centre_x = self.surface.get_width() // 2
        self.surface.blit(title, title.get_rect(center=(centre_x, 300)))
        self.surface.blit(subtitle, subtitle.get_rect(center=(centre_x, 350)))
        self.surface.blit(hint, hint.get_rect(center=(centre_x, 380)))
        for index, message in enumerate(self.messages[-3:]):
            line = small.render(message, True, (222, 120, 120))
            self.surface.blit(line, (24, 24 + index * 26))
        pygame.display.flip()

    def tick(self) -> None:
        """Process one frame. Separated from ``run`` so tests can drive frames."""
        self.handle_events()
        self.draw()
        self.clock.tick(TARGET_FPS)

    def run(self) -> None:
        logger.info("Apex Horizon %s starting.", __version__)
        while self.running:
            self.tick()
        self.shutdown()

    def shutdown(self) -> None:
        logger.info("Apex Horizon shutting down.")
        pygame.quit()


def run_game() -> None:
    """Create the window and run until the player exits."""
    GameWindow().run()
