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
from ..engine.simulation import SimulationEngine

logger = get_logger(__name__)

WINDOW_TITLE = "Apex Horizon"
# Placeholder window size; the real design canvas is defined with the UI system.
WINDOW_SIZE = (1280, 720)
TARGET_FPS = 60

# Neutral, professional placeholder palette (V1.15: clean, modern, minimalistic).
BACKGROUND = (18, 20, 24)
TEXT = (232, 235, 240)
MUTED = (138, 146, 158)

# Keyboard shortcuts for simulation speed, per V27.9 and the x1/x2/x3 of V13.5.
SPEED_KEYS = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}


class GameWindow:
    """Creates the window and runs the outer frame loop."""

    def __init__(self, size: tuple[int, int] = WINDOW_SIZE, engine: SimulationEngine | None = None):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.surface = pygame.display.set_mode(size)
        self.clock = pygame.time.Clock()
        self.running = True
        self.messages: list[str] = []
        # The shell drives the simulation but never reaches into it: it advances
        # time and reads state for display only, keeping game logic out of the
        # interface layer (V15.5).
        self.engine = engine or SimulationEngine()
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
            elif event.type == pygame.KEYDOWN and event.key in SPEED_KEYS:
                self.engine.clock.speed = SPEED_KEYS[event.key]

    def draw(self) -> None:
        self.surface.fill(BACKGROUND)
        font = pygame.font.SysFont(None, 48)
        small = pygame.font.SysFont(None, 24)
        centre_x = self.surface.get_width() // 2

        lines = [
            (font, f"{WINDOW_TITLE} {__version__}", TEXT, 260),
            (font, self.engine.date.label(), TEXT, 320),
            (small, f"Day {self.engine.date.day}  ·  Speed x{self.engine.clock.speed}", MUTED, 366),
            (small, "Press 1 / 2 / 3 to change speed, Esc to exit.", MUTED, 400),
        ]
        for surface_font, text, colour, y in lines:
            rendered = surface_font.render(text, True, colour)
            self.surface.blit(rendered, rendered.get_rect(center=(centre_x, y)))

        for index, message in enumerate(self.messages[-3:]):
            line = small.render(message, True, (222, 120, 120))
            self.surface.blit(line, (24, 24 + index * 26))
        pygame.display.flip()

    def tick(self) -> None:
        """Process one frame. Separated from ``run`` so tests can drive frames."""
        # Milliseconds since the previous frame; the engine converts elapsed real
        # time into whole in-game days itself, so rendering pace never affects
        # simulation pace (V13.29).
        delta_ms = self.clock.tick(TARGET_FPS)
        self.handle_events()
        self.engine.update(delta_ms / 1000.0)
        self.draw()

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
