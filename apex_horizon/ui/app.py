"""The application.

Owns the window, the running simulation, and the navigation between pages. It
reads game state for display and asks systems to do things, but contains no
gameplay logic of its own (V15.5).

Simulation pacing lives with the engine (V13.29), so the frame rate never
affects how fast the world moves; this class only forwards elapsed real time and
holds time still while a decision is open (V13.20).
"""

from __future__ import annotations

from random import Random

import pygame

from .. import __version__
from ..engine.company import Player
from ..engine.config import get_config
from ..engine.economy import BankingSystem, EconomySystem
from ..engine.errors import subscribe_error_notifier
from ..engine.logging_setup import get_logger
from ..engine.market import MarketSystem
from ..engine.simulation import PeriodBoundary, SimulationEngine
from ..engine.values import Money
from ..engine.world import WorldGenerator, generate_world
from . import theme
from .chrome import NAV_ITEMS, Breadcrumb, NotificationCentre, SaveIndicator, Sidebar, TimeControls
from .context import GameContext
from .pages import (
    CompanyDetailPage,
    CompanyPage,
    DashboardPage,
    FinancePage,
    InvestmentsPage,
    MarketPage,
    NewsPage,
    SettingsPage,
    UnlockTreePage,
)
from .popups import PopupAction, PopupManager, PromptPopup
from .widgets import draw_text

logger = get_logger(__name__)

WINDOW_TITLE = "Apex Horizon"
WINDOW_SIZE = (1440, 860)
MINIMUM_SIZE = (1100, 680)
TARGET_FPS = 60

# Keyboard shortcuts for simulation speed (V27.9, V13.5).
SPEED_KEYS = {pygame.K_1: 1, pygame.K_2: 2, pygame.K_3: 3}


class GameApp:
    """The Apex Horizon application."""

    def __init__(self, size: tuple[int, int] = WINDOW_SIZE, *, seed: int | None = None):
        pygame.init()
        pygame.display.set_caption(WINDOW_TITLE)
        self.surface = pygame.display.set_mode(size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.fonts = theme.Fonts.load()
        self.running = True

        self.context = GameContext()
        self._build_world(seed)

        self.sidebar = Sidebar()
        self.breadcrumb = Breadcrumb()
        self.time_controls = TimeControls(tuple(
            int(value) for value in get_config().get_list("simulation.speed_options")
        ))
        self.save_indicator = SaveIndicator()
        self.notifications = NotificationCentre()
        self.popups = PopupManager()

        market_page = MarketPage(self.context)
        self.pages = {
            "dashboard": DashboardPage(self.context),
            "company": CompanyPage(self.context),
            "investments": InvestmentsPage(self.context),
            "market": market_page,
            "market:company": CompanyDetailPage(self.context, market_page),
            "news": NewsPage(self.context),
            "unlocks": UnlockTreePage(self.context),
            "finance": FinancePage(self.context),
            "settings": SettingsPage(self.context),
        }
        self.current_key = "dashboard"

        subscribe_error_notifier(self._on_engine_error)

    # -- setup -------------------------------------------------------------
    def _build_world(self, seed: int | None) -> None:
        """Create a new world and start its simulation."""
        config = get_config()
        seed = seed if seed is not None else config.get_int("simulation.default_random_seed")

        world, allocator, names = generate_world(seed)
        economy = EconomySystem()
        generator = WorldGenerator(Random(seed), allocator=allocator, names=names)
        market = MarketSystem(world, generator=generator, economy=economy)
        market.populate(Random(seed))
        banking = BankingSystem(world, economy)
        banking.populate(Random(seed))

        engine = SimulationEngine(seed=seed)
        economy.register(engine)
        banking.register(engine)
        market.register(engine)

        player = Player("Founder", allocator=allocator)

        self.context.engine = engine
        self.context.world = world
        self.context.economy = economy
        self.context.market = market
        self.context.banking = banking
        self.context.player = player

        # Tell the player when the economy turns; news proper arrives later.
        engine.register_boundary(PeriodBoundary.MONTH, self._announce_economy)
        self._last_reported_state = economy.state

    def _announce_economy(self, context) -> None:
        economy = self.context.economy
        if economy.state is not self._last_reported_state:
            self._last_reported_state = economy.state
            self.notifications.push(
                f"The economy has moved to {economy.state}.",
                pygame.time.get_ticks(),
                emphasis=True,
            )

    def _on_engine_error(self, message: str) -> None:
        self.notifications.push(message, pygame.time.get_ticks(), emphasis=True)

    # -- navigation --------------------------------------------------------
    @property
    def page(self):
        return self.pages[self.current_key]

    def navigate(self, key: str) -> None:
        if key in self.pages and key != self.current_key:
            self.current_key = key
            self.page.on_show()
        # Sub-pages keep their parent's sidebar entry highlighted.
        self.sidebar.active = key.split(":")[0]

    # -- events ------------------------------------------------------------
    def handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                continue
            if event.type == pygame.VIDEORESIZE:
                width = max(MINIMUM_SIZE[0], event.w)
                height = max(MINIMUM_SIZE[1], event.h)
                self.surface = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                continue

            # A popup is modal: it takes every event while it is open (V14.15).
            if self.popups.is_open:
                self.popups.handle_event(event)
                continue

            if event.type == pygame.KEYDOWN and event.key in SPEED_KEYS:
                self.context.engine.clock.speed = SPEED_KEYS[event.key]
                continue

            if self.sidebar.handle_event(event):
                destination = self.sidebar.take_request()
                if destination:
                    self.navigate(destination)
                continue
            if self.breadcrumb.handle_event(event):
                destination = self.breadcrumb.take_request()
                if destination:
                    self.navigate(destination)
                continue
            if self.time_controls.handle_event(event):
                speed = self.time_controls.take_request()
                if speed:
                    self.context.engine.clock.speed = speed
                continue

            self.page.handle_event(event)
            self._collect_page_requests()

    def _collect_page_requests(self) -> None:
        """Act on anything a page asked for while handling its own events."""
        page = self.page
        if page.navigate_to:
            destination, page.navigate_to = page.navigate_to, None
            self.navigate(destination)
        if isinstance(page, CompanyPage) and page.take_found_request():
            self._prompt_found_company()
        if isinstance(page, SettingsPage):
            speed = page.take_speed_request()
            if speed:
                self.context.engine.clock.speed = speed
            if page.take_exit_request():
                self._prompt_exit()

    def _prompt_found_company(self) -> None:
        """Ask the player to name their company (V3.3)."""
        player = self.context.player
        popup = PromptPopup(
            title="Found your company",
            message=(
                f"Founding costs {player.founding_cost.format(decimals=0)}, which becomes "
                "your company's opening capital. Choose a name."
            ),
            placeholder="Company name",
            actions=[PopupAction("cancel", "Cancel"), PopupAction("found", "Found", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "found":
                return
            name = popup.text.strip()
            company, message = player.found_company(name, self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=company is not None)
            if company is not None:
                company.register(self.context.engine)
                self.save_indicator.unsaved = True

        self.popups.open(popup, on_choice)

    def _prompt_exit(self) -> None:
        popup_actions = [PopupAction("stay", "Keep playing"),
                         PopupAction("exit", "Save & Exit", primary=True)]
        from .popups import Popup

        popup = Popup(
            title="Save & Exit",
            message=(
                "The Save System arrives in a later milestone, so this will leave "
                "without saving. Continue?"
            ),
            actions=popup_actions,
        )

        def on_choice(choice: str) -> None:
            if choice == "exit":
                self.running = False

        self.popups.open(popup, on_choice)

    # -- frame -------------------------------------------------------------
    def tick(self) -> None:
        delta_ms = self.clock.tick(TARGET_FPS)
        now = pygame.time.get_ticks()
        self.handle_events()

        # Every popup pauses the simulation (V13.20, V14.15).
        clock = self.context.engine.clock
        if self.popups.is_open:
            clock.pause()
        else:
            clock.resume()
        self.context.engine.update(delta_ms / 1000.0)

        self.notifications.update(now)
        self.draw(now)

    def draw(self, now_ms: int) -> None:
        mouse = pygame.mouse.get_pos()
        self.surface.fill(theme.BACKGROUND)

        self.sidebar.active = self.current_key.split(":")[0]
        self.sidebar.draw(self.surface, self.fonts, mouse)
        self._draw_topbar(mouse)

        content = pygame.Rect(
            theme.SIDEBAR_WIDTH + theme.PAGE_PADDING,
            theme.TOPBAR_HEIGHT + theme.PAGE_PADDING - 8,
            self.surface.get_width() - theme.SIDEBAR_WIDTH - theme.PAGE_PADDING * 2,
            self.surface.get_height() - theme.TOPBAR_HEIGHT - theme.PAGE_PADDING,
        )
        self.page.draw(self.surface, content, self.fonts, mouse, self.breadcrumb)

        self.notifications.draw(self.surface, self.fonts, now_ms)
        self.sidebar.draw_tooltip(self.surface, self.fonts)
        self.popups.draw(self.surface, self.fonts, mouse)
        pygame.display.flip()

    def _draw_topbar(self, mouse) -> None:
        rect = pygame.Rect(theme.SIDEBAR_WIDTH, 0,
                           self.surface.get_width() - theme.SIDEBAR_WIDTH, theme.TOPBAR_HEIGHT)
        pygame.draw.rect(self.surface, theme.SURFACE, rect)
        pygame.draw.line(self.surface, theme.BORDER,
                         (rect.left, rect.bottom), (rect.right, rect.bottom))

        engine = self.context.engine
        draw_text(self.surface, self.fonts.small, engine.date.label(),
                  (rect.left + theme.PAGE_PADDING, rect.centery), theme.TEXT,
                  baseline="middle")

        economy = self.context.economy
        if economy is not None:
            draw_text(self.surface, self.fonts.small, str(economy.state),
                      (rect.left + theme.PAGE_PADDING + 230, rect.centery),
                      theme.TEXT_MUTED, baseline="middle")

        speed_rect = self.time_controls.draw(
            self.surface, self.fonts, mouse, rect.right - theme.PAGE_PADDING,
            rect.centery, engine.clock.speed, engine.clock.paused,
        )
        self.save_indicator.draw(self.surface, self.fonts,
                                 speed_rect.left - 24, rect.centery)

    # -- lifecycle ---------------------------------------------------------
    def run(self) -> None:
        logger.info("Apex Horizon %s starting.", __version__)
        self.notifications.push(
            "Welcome to Apex Horizon. Found a company from the Company page.",
            pygame.time.get_ticks(),
        )
        while self.running:
            self.tick()
        self.shutdown()

    def shutdown(self) -> None:
        logger.info("Apex Horizon shutting down.")
        pygame.quit()


def run_game() -> None:
    GameApp().run()


# Keeps the sidebar destinations discoverable from the application module.
NAVIGATION = NAV_ITEMS
COMPANY_START_CASH = Money(0)
