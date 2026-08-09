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
from ..debug import DebugConsole
from ..engine.ai import AICompanies
from ..engine.analytics import AnalyticsService, HistoryRecorder
from ..engine.company import Player
from ..engine.config import get_config
from ..engine.economy import BankingSystem, EconomySystem
from ..engine.errors import subscribe_error_notifier
from ..engine.logging_setup import get_logger
from ..engine.market import MarketSystem
from ..engine.news import NewsSystem, NewsTier
from ..engine.save import SaveService
from ..engine.simulation import PeriodBoundary, SimulationEngine
from ..engine.statistics import LifetimeStatistics
from ..engine.unlocks import UnlockEffects
from ..engine.values import Money
from ..engine.world import WorldGenerator, generate_world
from . import theme
from .chrome import NAV_ITEMS, Breadcrumb, NotificationCentre, SaveIndicator, Sidebar, TimeControls
from .context import GameContext
from .pages import (
    CompanyDetailPage,
    CompanyPage,
    DashboardPage,
    EmployeeDetailPage,
    EmployeesPage,
    FinancePage,
    FundDetailPage,
    FundsPage,
    MarketPage,
    NewsPage,
    PortfolioPage,
    SettingsPage,
    SubsidiariesPage,
    SubsidiaryDetailPage,
    UnlockTreePage,
)
from .popups import Popup, PopupAction, PopupManager, PromptPopup
from .start_menu import EXIT, LOAD_GAME, NEW_GAME, SETTINGS, StartMenu
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

    def __init__(self, size: tuple[int, int] = WINDOW_SIZE, *, seed: int | None = None,
                 start_in_menu: bool = False):
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
        employees_page = EmployeesPage(self.context)
        subsidiaries_page = SubsidiariesPage(self.context)
        funds_page = FundsPage(self.context)
        self.pages = {
            "dashboard": DashboardPage(self.context),
            "company": CompanyPage(self.context),
            "company:employees": employees_page,
            "company:employee": EmployeeDetailPage(self.context, employees_page),
            "company:subsidiaries": subsidiaries_page,
            "company:subsidiary": SubsidiaryDetailPage(self.context, subsidiaries_page),
            "company:funds": funds_page,
            "company:fund": FundDetailPage(self.context, funds_page),
            "portfolio": PortfolioPage(self.context),
            "market": market_page,
            "market:company": CompanyDetailPage(self.context, market_page),
            "news": NewsPage(self.context),
            "unlocks": UnlockTreePage(self.context),
            "finance": FinancePage(self.context),
            "settings": SettingsPage(self.context),
        }
        self.current_key = "dashboard"

        self.saves = SaveService(self.context)
        self.saves.on_autosave.append(self._on_autosave)
        self.context.saves = self.saves
        self.current_slot: str = "1"

        subscribe_error_notifier(self._on_engine_error)

        # V16.4 returns the player to a Main Menu on leaving, so there has to be
        # one. The game opens on it; a directly constructed application starts
        # in play, which is what every test wants.
        self.menu = StartMenu(self.saves)
        self.in_menu = start_in_menu

        # Developer commands from the launching terminal (V15.18). Inert when
        # there is no terminal to read, which is every test and CI run.
        self.console = DebugConsole(self.context, app=self)
        self.console.start()

    def _on_autosave(self, message: str) -> None:
        """A brief, non-pausing confirmation that an autosave completed (V16.24)."""
        self.notifications.push(message, pygame.time.get_ticks())

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
        news = NewsSystem(world, market, economy, allocator=allocator)
        market.news = news

        # The world's other investment companies, so it is inhabited rather than
        # a backdrop (V26.2, V4.10).
        ai = AICompanies(allocator=allocator)
        ai.populate(Random(seed + 1), market, names)

        engine = SimulationEngine(seed=seed)
        news.register(engine)
        economy.register(engine)
        banking.register(engine)
        ai.register(engine)
        market.register(engine)

        player = Player("Founder", allocator=allocator)
        # The player is an individual investor before they are a CEO (V1.19),
        # so they can trade their own money from the first day.
        player.attach_market(market)

        self.context.engine = engine
        self.context.world = world
        self.context.economy = economy
        self.context.market = market
        self.context.banking = banking
        self.context.player = player
        self.context.allocator = allocator
        self.context.names = names
        self.context.news = news
        self.context.ai = ai
        news.on_article.append(self._on_article)

        # Analytics read the world back to the player; the recorder is the only
        # part that touches the simulation, and only to remember (V9.10, V9.22).
        history = HistoryRecorder(self.context)
        history.register(engine)
        self.context.analytics = AnalyticsService(self.context, history=history)

        # What the player has unlocked decides what every system offers (V6.3).
        self.effects = UnlockEffects(player.unlocks)
        self.effects.apply(self.context)

        # Cumulative records for the whole playthrough (V28.7). Fed through the
        # callbacks systems already expose, so none of them knows it exists.
        self.context.statistics = LifetimeStatistics()
        player.unlocks.on_unlocked.append(self.context.statistics.record_unlock)
        if player.portfolio is not None:
            player.portfolio.on_trade.append(self.context.statistics.record_trade)

        # Tell the player when the economy turns; news proper arrives later.
        engine.register_boundary(PeriodBoundary.MONTH, self._announce_economy)
        engine.register_boundary(PeriodBoundary.MONTH, self._record_high_water_marks)
        self._last_reported_state = economy.state

    def _observe_company(self, company) -> None:
        """Point the lifetime counters at a newly founded company (V28.7)."""
        statistics = self.context.statistics
        statistics.record_founding(company)
        company.employees.on_hire.append(statistics.record_hire)
        company.on_bankruptcy.append(statistics.record_bankruptcy)
        if company.investments is not None:
            company.investments.on_invested.append(statistics.record_invested)
            company.investments.on_closed.append(statistics.record_closed_position)
        if company.subsidiaries is not None:
            company.subsidiaries.on_acquired.append(statistics.record_acquisition)
        if company.funds is not None:
            company.funds.on_created.append(statistics.record_fund)
            company.funds.on_created.append(self._observe_fund)

    def _observe_fund(self, fund) -> None:
        """Count the fees a newly opened fund goes on to pay (V28.7)."""
        fund.on_fee.append(self.context.statistics.record_fee)

    def _record_high_water_marks(self, context) -> None:
        """Highest net worth and company value only ever rise (V28.7)."""
        statistics = self.context.statistics
        company = self.context.company
        statistics.observe(
            net_worth=self.context.player.net_worth(),
            company_value=company.value() if company else None,
        )

    def _on_article(self, article) -> None:
        """Interrupt the player only for a story that warrants it (V14.16).

        The world publishes something most days, and pushing every routine
        company move as a notification buries the screen in toasts — which
        makes the one story that mattered no easier to notice than the rest.
        V10.14 reserves the interruption for genuinely significant events, so
        only breaking news and shifts in the economy arrive this way; everything
        else waits on the News page, where V10.15 keeps it readable.
        """
        if not (article.is_breaking or article.tier is NewsTier.ECONOMIC):
            return
        self.notifications.push(
            article.headline, pygame.time.get_ticks(), emphasis=article.is_breaking
        )

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
                if self.sidebar.take_exit_request():
                    # Leaving is an action, not a destination (V16.4).
                    self._prompt_exit()
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
        if isinstance(page, CompanyPage):
            if page.take_found_request():
                self._prompt_found_company()
            if page.take_employees_request():
                self.navigate("company:employees")
            if page.take_subsidiaries_request():
                self.navigate("company:subsidiaries")
            destination = page.take_destination_request()
            if destination:
                self.navigate(destination)
        if isinstance(page, EmployeesPage):
            self._handle_employees_page(page)
        if isinstance(page, EmployeeDetailPage):
            self._handle_employee_detail(page)
        if isinstance(page, CompanyDetailPage):
            trade = page.take_trade_request()
            if trade:
                self._prompt_trade(*trade)
            target = page.take_acquire_request()
            if target:
                self._prompt_acquire(target)
        if isinstance(page, UnlockTreePage):
            key = page.take_unlock_request()
            if key:
                self._prompt_unlock(key)
        if isinstance(page, FundsPage) and page.take_create_request():
            self._prompt_open_fund()
        if isinstance(page, SettingsPage):
            speed = page.take_speed_request()
            if speed:
                self.context.engine.clock.speed = speed
            if page.take_exit_request():
                self._prompt_exit()
            request = page.take_slot_request()
            if request:
                slot, action = request
                if action == "save":
                    self._save_slot(slot)
                else:
                    self._prompt_load(slot)

    def _handle_employees_page(self, page) -> None:
        """Recruiting and hiring (V5.3)."""
        roster = page.roster
        if roster is None:
            return
        if page.take_recruit_request():
            roster.refresh_applicants(
                self.context.engine.rng, self.context.names,
                self.context.allocator, self.context.engine.date.day,
            )
            self.saves.mark_changed()
        applicant_id = page.take_hire_request()
        if applicant_id:
            applicant = next((a for a in roster.applicants if a.id == applicant_id), None)
            if applicant is not None:
                ok, message = roster.hire(applicant, self.context.engine.date.day)
                self.notifications.push(message, pygame.time.get_ticks(), emphasis=not ok)
                if ok:
                    self.saves.mark_changed()

    def _handle_employee_detail(self, page) -> None:
        """Assignment, training, pay and dismissal (V5.5, V5.9, V5.11)."""
        request = page.take_request()
        employee = page.employee
        if request is None or employee is None:
            return
        roster = page.employees_page.roster
        day = self.context.engine.date.day
        action, value = request

        if action == "department":
            slot, department = value
            # Swap so all three departments stay assigned exactly once (V5.5).
            order = list(employee.priorities)
            index = ("primary", "secondary", "third").index(slot)
            other = order.index(department)
            order[index], order[other] = order[other], order[index]
            roster.assign_departments(employee, *order, day)
            self.saves.mark_changed()
        elif action == "train":
            ok, message = roster.start_training(employee, value, day)
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=not ok)
            self.saves.mark_changed()
        elif action == "raise":
            _, message = roster.set_salary(employee, employee.expected_salary(), day)
            self.notifications.push(message, pygame.time.get_ticks())
            self.saves.mark_changed()
        elif action == "dismiss":
            self._prompt_dismiss(roster, employee)

    def _prompt_dismiss(self, roster, employee) -> None:
        popup = Popup(
            title=f"Dismiss {employee.name}?",
            message="They will leave the company immediately. This cannot be undone.",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("dismiss", "Dismiss", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "dismiss":
                return
            ok, message = roster.fire(employee)
            self.notifications.push(message, pygame.time.get_ticks(), emphasis=not ok)
            if ok:
                self.saves.mark_changed()
                self.navigate("company:employees")

        self.popups.open(popup, on_choice)

    def _prompt_found_company(self) -> None:
        """Ask the player to name their company (V3.3).

        Founding is refused here rather than at the button so the player is told
        *why* — needing the Create Company unlock (V6.2) reads as progression,
        while a dead button reads as a broken screen (V14.26).
        """
        player = self.context.player
        allowed, reason = player.can_found_company()
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return
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
                company.attach_market(self.context.market, self.context.allocator)
                company.register(self.context.engine)
                # A new company starts at whatever level the tree already grants.
                self.effects.apply(self.context)
                self._observe_company(company)
                # Founding is a major decision, so the moment before it is kept
                # (V16.6) and the game is marked as having unsaved changes.
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_trade(self, action: str, company_id: str) -> None:
        """Buy or sell shares with the player's own money (V1.19, V3.4)."""
        portfolio = self.context.portfolio
        record = self.context.world.company_by_id(company_id)
        listing = self.context.market.listing_for(company_id)
        if portfolio is None or record is None or listing is None:
            return

        buying = action == "buy"
        if buying:
            limit = portfolio.max_affordable(company_id)
            message = (
                f"{record.name} trades at {listing.price.format()}. "
                f"You can afford {limit:,} shares."
            )
        else:
            limit = portfolio.shares_of(company_id)
            message = (
                f"{record.name} trades at {listing.price.format()}. "
                f"You hold {limit:,} shares."
            )
        popup = PromptPopup(
            title=f"{'Buy' if buying else 'Sell'} {record.name}",
            message=message,
            placeholder="Number of shares",
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction(action, "Buy" if buying else "Sell", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != action:
                return
            try:
                shares = int(popup.text.strip().replace(",", ""))
            except ValueError:
                self.notifications.push("Enter a number of shares.",
                                        pygame.time.get_ticks(), emphasis=True)
                return
            day = self.context.engine.date.day
            ok, result = (portfolio.buy(company_id, shares, day) if buying
                          else portfolio.sell(company_id, shares, day))
            self.notifications.push(result, pygame.time.get_ticks(), emphasis=not ok)
            if ok:
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_acquire(self, company_id: str) -> None:
        """Buy a company outright, in company cash (V12.4, V12.22).

        Acquiring is permanent and paid for in full, so it is exactly the kind
        of irreversible decision V16.6 wants the moment before kept for.
        """
        company = self.context.company
        book = getattr(company, "subsidiaries", None)
        record = self.context.world.company_by_id(company_id)
        if book is None or record is None:
            return
        allowed, reason = book.can_acquire(company_id)
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        price = book.price_of(company_id)
        popup = Popup(
            title=f"Acquire {record.name}",
            message=(
                f"{record.name} would cost {price.format(decimals=0)}, paid in full "
                f"from company cash. It becomes a subsidiary, keeps operating in "
                f"{record.industry.value}, and stops trading on the market.\n\n"
                "This cannot be undone."
            ),
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction("acquire", "Acquire", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != "acquire":
                return
            self.saves.autosave_before(f"acquiring {record.name}")
            subsidiary, message = book.acquire(company_id, self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(),
                                    emphasis=subsidiary is not None)
            if subsidiary is not None:
                self.saves.mark_changed()
                self.navigate("company:subsidiaries")

        self.popups.open(popup, on_choice)

    def _prompt_open_fund(self) -> None:
        """Name and open an investment fund (V11.6)."""
        company = self.context.company
        book = getattr(company, "funds", None)
        if book is None:
            return
        allowed, reason = book.can_create()
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        popup = PromptPopup(
            title="Open an investment fund",
            message=(
                "A fund invests money entrusted by outside investors. That money "
                "is theirs, not yours — your company earns a fee for managing it "
                "well. Choose a name."
            ),
            placeholder="Fund name",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("open", "Open", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "open":
                return
            fund, message = book.create(popup.text.strip(), self.context.engine.date.day)
            self.notifications.push(message, pygame.time.get_ticks(),
                                    emphasis=fund is not None)
            if fund is not None:
                fund.register(self.context.engine)
                self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _prompt_unlock(self, key: str) -> None:
        """Buy an unlock with personal cash (V6.2)."""
        player = self.context.player
        tree = self.context.unlocks
        if tree is None:
            return
        unlock = tree.by_key.get(key)
        if unlock is None:
            return
        allowed, reason = tree.can_purchase(key, player.cash)
        if not allowed:
            self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
            return

        cost = tree.cost_of(key)
        popup = Popup(
            title=f"Unlock {unlock.name}",
            message=f"{unlock.description}\n\nThis costs {cost.format(decimals=0)}.",
            actions=[
                PopupAction("cancel", "Cancel"),
                PopupAction("unlock", "Unlock", primary=True),
            ],
        )

        def on_choice(choice: str) -> None:
            if choice != "unlock":
                return
            # Re-check: time keeps running while a popup is open only for the
            # simulation the player paused, so cash may have changed.
            allowed, reason = tree.can_purchase(key, player.cash)
            if not allowed:
                self.notifications.push(reason, pygame.time.get_ticks(), emphasis=True)
                return
            player.cash = player.cash - tree.cost_of(key)
            tree.unlock(key)
            self.effects.apply(self.context)
            self.notifications.push(f"{unlock.name} unlocked.",
                                    pygame.time.get_ticks(), emphasis=True)
            self.saves.mark_changed()

        self.popups.open(popup, on_choice)

    def _save_slot(self, slot: str) -> None:
        """Write the game to a slot and report the outcome."""
        result = self.saves.save_to_slot(
            slot, name=self.context.company.name if self.context.company else "Apex Horizon"
        )
        self.current_slot = slot
        self.notifications.push(result.message, pygame.time.get_ticks(),
                                emphasis=not result.ok)

    def _prompt_load(self, slot: str) -> None:
        """Confirm before replacing the running game with a saved one."""
        info = self.saves.store.info(slot)
        popup = Popup(
            title=f"Load {info.label}?",
            message=f"{info.describe()} This will replace your current game.",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("load", "Load", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "load":
                return
            outcome = self.saves.load_from_slot(slot)
            if outcome.ok:
                self.current_slot = slot
                self._rebind_after_load()
                self.notifications.push(f"Loaded {info.label}.", pygame.time.get_ticks())
            elif outcome.needs_confirmation:
                # V16.14: repair did not succeed, so the player is asked whether
                # to attempt the load anyway rather than simply refused.
                self._prompt_damaged_load(slot, outcome.describe())
            else:
                self.notifications.push(
                    f"Could not load: {outcome.describe()}",
                    pygame.time.get_ticks(), emphasis=True,
                )

        self.popups.open(popup, on_choice)

    def _prompt_damaged_load(self, slot: str, problem: str) -> None:
        popup = Popup(
            title="This save is damaged",
            message=f"{problem} Would you like to try loading it anyway?",
            actions=[PopupAction("cancel", "Cancel"),
                     PopupAction("try", "Try anyway", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "try":
                return
            outcome = self.saves.load_from_slot(slot, allow_damaged=True)
            if outcome.ok:
                self._rebind_after_load()
            self.notifications.push(
                outcome.describe() if outcome.ok else f"Could not load: {outcome.describe()}",
                pygame.time.get_ticks(), emphasis=not outcome.ok,
            )

        self.popups.open(popup, on_choice)

    def _rebind_after_load(self) -> None:
        """Point the interface at the systems the loaded game created."""
        self.saves.on_autosave = [self._on_autosave]
        self.context.saves = self.saves
        # The loaded game brought its own player, and so its own unlock tree;
        # re-applying the effects makes the restored world behave exactly as the
        # saved one did (V6.3, V16.28).
        self.effects = UnlockEffects(self.context.player.unlocks)
        self.effects.apply(self.context)
        self.context.news.on_article = [self._on_article]
        self._last_reported_state = self.context.economy.state
        self.context.engine.register_boundary(PeriodBoundary.MONTH, self._announce_economy)
        for page in self.pages.values():
            page.context = self.context
        market_page = self.pages["market"]
        market_page.selected_company_id = None
        market_page.table.page = 0
        self.navigate("dashboard")

    def _prompt_exit(self) -> None:
        """The Save & Exit workflow of V16.4.

        Selecting it pauses the simulation, attempts the save, and only leaves
        if that succeeds; a failed save returns the player to the running game
        with an error so another attempt can be made, rather than losing the
        session.
        """
        popup = Popup(
            title="Save & Exit",
            message=(
                f"Your game will be saved to {self.saves.store.info(self.current_slot).label} "
                "before leaving."
            ),
            actions=[PopupAction("stay", "Keep playing"),
                     PopupAction("exit", "Save & Exit", primary=True)],
        )

        def on_choice(choice: str) -> None:
            if choice != "exit":
                return
            result = self.saves.save_to_slot(
                self.current_slot,
                name=self.context.company.name if self.context.company else "Apex Horizon",
            )
            if result.ok:
                self._return_to_menu(f"Saved to {self.saves.store.info(self.current_slot).label}.")
            else:
                self.popups.open(Popup(
                    title="Saving failed",
                    message=f"{result.message} Your game has not been closed.",
                    actions=[PopupAction("ok", "Continue playing", primary=True)],
                ))

        self.popups.open(popup, on_choice)

    # -- the start menu (V16.4) --------------------------------------------
    def _return_to_menu(self, message: str = "") -> None:
        """Leave the session for the Main Menu, having saved (V16.4 step 5)."""
        self.in_menu = True
        self.menu.showing_loads = False
        self.menu.message = message
        self.notifications.items.clear()
        logger.info("Returned to the Main Menu.")

    def _menu_tick(self, now_ms: int) -> None:
        """One frame of the Main Menu: no simulation runs while it is open."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return
            if event.type == pygame.VIDEORESIZE:
                width = max(event.w, MINIMUM_SIZE[0])
                height = max(event.h, MINIMUM_SIZE[1])
                self.surface = pygame.display.set_mode((width, height), pygame.RESIZABLE)
                continue
            self.menu.handle_event(event)

        request = self.menu.take_request()
        if request == NEW_GAME:
            self._start_new_game()
        elif request == SETTINGS:
            self.in_menu = False
            self.navigate("settings")
        elif request == EXIT:
            self.running = False
        elif isinstance(request, tuple) and request[0] == LOAD_GAME:
            self._load_from_menu(request[1])

        self.menu.draw(self.surface, self.fonts, pygame.mouse.get_pos())
        self.popups.draw(self.surface, self.fonts, pygame.mouse.get_pos())
        pygame.display.flip()

    def _start_new_game(self) -> None:
        """Begin a fresh world (V16.4: the menu leads back into gameplay)."""
        import secrets

        self._build_world(secrets.randbelow(2**31))
        self.saves = SaveService(self.context)
        self.saves.on_autosave = [self._on_autosave]
        self.context.saves = self.saves
        self.menu.saves = self.saves
        self.effects = UnlockEffects(self.context.player.unlocks)
        self.effects.apply(self.context)
        self.context.statistics = LifetimeStatistics()
        self.context.player.unlocks.on_unlocked.append(
            self.context.statistics.record_unlock)
        if self.context.player.portfolio is not None:
            self.context.player.portfolio.on_trade.append(
                self.context.statistics.record_trade)
        for page in self.pages.values():
            page.context = self.context
        self.console.context = self.context
        self.in_menu = False
        self.menu.message = ""
        self.navigate("dashboard")
        self.notifications.push("A new game has begun.", pygame.time.get_ticks())

    def _load_from_menu(self, slot: str) -> None:
        """Open a saved game from the menu, reporting honestly if it fails."""
        outcome = self.saves.load_from_slot(slot)
        if outcome.ok:
            self._rebind_after_load()
            self.current_slot = slot
            self.in_menu = False
            self.menu.message = ""
            self.notifications.push(f"Loaded {self.saves.store.info(slot).label}.",
                                    pygame.time.get_ticks())
            return
        # V16.13-16.14: an unreadable save is reported, never silently opened.
        self.menu.message = outcome.describe()
        self.menu.showing_loads = False

    # -- frame -------------------------------------------------------------
    def tick(self) -> None:
        if self.in_menu:
            self.clock.tick(TARGET_FPS)
            self._menu_tick(pygame.time.get_ticks())
            return
        delta_ms = self.clock.tick(TARGET_FPS)
        now = pygame.time.get_ticks()
        self.handle_events()
        # Developer commands run here rather than on the reader thread, so one
        # can never change the world halfway through a frame (V15.18).
        self.console.poll()

        # Every popup pauses the simulation (V13.20, V14.15).
        clock = self.context.engine.clock
        if self.popups.is_open:
            clock.pause()
        else:
            clock.resume()
        self.context.engine.update(delta_ms / 1000.0)

        if not self.popups.is_open:
            self.saves.record_playtime(delta_ms / 1000.0)
        self.save_indicator.unsaved = self.saves.unsaved_changes
        self.notifications.update(now)
        self.draw(now)

    def draw(self, now_ms: int) -> None:
        mouse = pygame.mouse.get_pos()
        self.surface.fill(theme.BACKGROUND)

        self.sidebar.active = self.current_key.split(":")[0]
        self.sidebar.draw(self.surface, self.fonts, mouse, now_ms)
        # The page gives way to the sidebar rather than being covered by it, so
        # expanding never hides what the player was reading.
        sidebar_width = self.sidebar.width(now_ms)
        self._draw_topbar(mouse, sidebar_width)

        content = pygame.Rect(
            sidebar_width + theme.PAGE_PADDING,
            theme.TOPBAR_HEIGHT + theme.PAGE_PADDING - 8,
            self.surface.get_width() - sidebar_width - theme.PAGE_PADDING * 2,
            self.surface.get_height() - theme.TOPBAR_HEIGHT - theme.PAGE_PADDING,
        )
        self.page.draw(self.surface, content, self.fonts, mouse, self.breadcrumb)

        overlays = getattr(self.page, "draw_overlays", None)
        if overlays is not None:
            overlays(self.surface, self.fonts, mouse)
        self.notifications.draw(self.surface, self.fonts, now_ms)
        self.sidebar.draw_tooltip(self.surface, self.fonts)
        self.popups.draw(self.surface, self.fonts, mouse)
        pygame.display.flip()

    def _draw_topbar(self, mouse, sidebar_width: int = theme.SIDEBAR_WIDTH) -> None:
        rect = pygame.Rect(sidebar_width, 0,
                           self.surface.get_width() - sidebar_width, theme.TOPBAR_HEIGHT)
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
        if not self.in_menu:
            self.notifications.push(
                "Welcome to Apex Horizon. Found a company from the Company page.",
                pygame.time.get_ticks(),
            )
        while self.running:
            self.tick()
        self.shutdown()

    def shutdown(self) -> None:
        logger.info("Apex Horizon shutting down.")
        self.console.stop()
        pygame.quit()


def run_game() -> None:
    """Launch the game, which opens on the Main Menu (V16.4)."""
    GameApp(start_in_menu=True).run()


# Keeps the sidebar destinations discoverable from the application module.
NAVIGATION = NAV_ITEMS
COMPANY_START_CASH = Money(0)
