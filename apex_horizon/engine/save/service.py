"""Saving and loading a game.

Design Bible V16.11 requires everything affecting gameplay to be saved. This
module is the one place that knows which systems exist and how to gather their
state, so adding a system later means adding it here rather than touching the
save format (V16.33).

Autosaving follows V16.5 — every in-game month by default, adjustable — and
V16.6, which additionally asks for an autosave immediately *before* a major
irreversible decision, so the player always has the moment before it to return
to. Only one rolling autosave is kept (V16.7).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from random import Random

from ... import __version__
from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import SimulationEngine
from ..values import IdAllocator, now_iso
from .format import SaveDocument, SaveMetadata, SaveSummary
from .slots import AUTOSAVE_SLOT, SaveStore, SlotInfo
from .validation import LoadOutcome, read_save

logger = get_logger(__name__)


@dataclass
class SaveResult:
    """The outcome of a save attempt (V16.4)."""

    ok: bool
    message: str
    path: Path | None = None


class SaveService:
    """Gathers game state into a save, and puts a save back into a game."""

    def __init__(self, context, *, store: SaveStore | None = None,
                 config: Config | None = None):
        self.context = context
        self.config = config or get_config()
        self.store = store or SaveStore(
            manual_slots=self.config.get_int("save.manual_slots")
        )
        self.metadata = SaveMetadata(game_version=__version__)
        self.playtime_seconds = 0.0
        #: Set whenever the world changes, cleared on save (V14.19, V13.22).
        self.unsaved_changes = False
        self._autosave_minutes = self.config.get_float("save.autosave_interval_minutes")
        self._seconds_since_autosave = 0.0
        #: Called with a message whenever an autosave completes (V16.24).
        self.on_autosave: list[Callable[[str], None]] = []

    # -- lifecycle ---------------------------------------------------------
    def record_playtime(self, seconds: float) -> None:
        """Count real time played, and autosave once enough of it has passed.

        Autosaving runs on the clock on the player's wall, not the one in the
        world. V16.5 has it happen every in-game month, but a month passes in
        twenty-eight seconds at normal speed and nine at triple, so the game
        spent its time writing saves nobody needed. What the interval was always
        for is how much of the player's *own* time a crash could cost them, and
        that is measured in real minutes (project-manager decision, 2026-08-09).

        The caller does not count time while a decision is open, so a game left
        sitting on a popup does not save itself over and over.
        """
        elapsed = max(0.0, seconds)
        self.playtime_seconds += elapsed
        if self._autosave_minutes <= 0:
            return
        self._seconds_since_autosave += elapsed
        if self._seconds_since_autosave >= self._autosave_minutes * 60:
            self._seconds_since_autosave = 0.0
            self.autosave()

    def mark_changed(self) -> None:
        self.unsaved_changes = True

    # -- gathering and applying state --------------------------------------
    def gather(self) -> SaveDocument:
        """Collect the state of every system (V16.11)."""
        context = self.context
        self.metadata.last_saved = now_iso()
        self.metadata.playtime_seconds = self.playtime_seconds

        state = {
            "engine": context.engine.state(),
            "world": context.world.state(),
            "market": context.market.state(),
            "economy": context.economy.state_data(),
            "banking": context.banking.state_data() if context.banking else {},
            "news": context.news.state() if getattr(context, "news", None) else {},
            "analytics": self._analytics_state(),
            "ai": context.ai.state() if getattr(context, "ai", None) else {},
            "statistics": (
                context.statistics.state()
                if getattr(context, "statistics", None) else {}
            ),
            "player": context.player.state(),
            "generation": {
                "allocator": getattr(context, "allocator", IdAllocator()).state(),
                "names": context.names.state() if getattr(context, "names", None) else {},
                "generator": (
                    context.market.generator.state()
                    if getattr(context.market, "generator", None) else {}
                ),
            },
        }
        return SaveDocument(metadata=self.metadata, summary=self._summary(), state=state)

    def _analytics_state(self) -> dict:
        """The analytics tier and the history behind it (V9.10, V16.11)."""
        service = getattr(self.context, "analytics", None)
        if service is None:
            return {}
        state = service.state()
        if service.history is not None:
            state["history"] = service.history.state()
        return state

    def _summary(self) -> SaveSummary:
        """The figures a slot shows without loading the world (V16.9)."""
        context = self.context
        player = context.player
        company = context.company
        date = context.engine.date
        return SaveSummary(
            money=str(player.cash.amount) if player else "0",
            net_worth=str(player.net_worth().amount) if player else "0",
            company_name=company.name if company else "",
            year=date.year(),
            month=date.month(),
            week=date.week_of_month(),
            day=date.day_of_week(),
        )

    def apply(self, document: SaveDocument) -> None:
        """Put a loaded save back into the running game.

        Systems are restored in dependency order: the world first, since the
        market and the player refer to its companies, then everything that
        reads from it.
        """
        from ..company import Player
        from ..economy import BankingSystem, EconomySystem
        from ..market import MarketSystem
        from ..world import NameGenerator, World, WorldGenerator

        state = document.state
        context = self.context

        world = World.from_state(state.get("world", {}))
        economy = EconomySystem(config=self.config)
        economy.restore(state.get("economy", {}))

        allocator = IdAllocator.from_state(
            state.get("generation", {}).get("allocator", {})
        )
        names = NameGenerator.from_state(
            Random(world.seed), state.get("generation", {}).get("names", {})
        )
        generator = WorldGenerator(Random(world.seed), allocator=allocator, names=names)
        generator.restore(state.get("generation", {}).get("generator", {}))

        market = MarketSystem(world, generator=generator, economy=economy,
                              config=self.config)
        market.restore(state.get("market", {}))

        banking = BankingSystem(world, economy, config=self.config)
        banking.restore(state.get("banking", {}))

        from ..news import NewsSystem

        news = NewsSystem(world, market, economy, allocator=allocator, config=self.config)
        news.restore(state.get("news", {}))
        market.news = news

        player = Player("Founder", config=self.config, allocator=allocator)
        player.restore(state.get("player", {}))
        # Personal holdings need a market to be priced against; restoring the
        # player happens first, so they are applied once the market exists.
        player.attach_market(market)

        engine = SimulationEngine(seed=world.seed, config=self.config)
        engine.restore(state.get("engine", {}))

        # Re-attach every system to the fresh engine.
        news.register(engine)
        economy.register(engine)
        banking.register(engine)
        market.register(engine)
        if player.company is not None and not player.company.bankrupt:
            player.company.attach_market(market, allocator)
            player.company.restore(state.get("player", {}).get("company", {}))
            player.company.register(engine)

        context.engine = engine
        context.world = world
        context.economy = economy
        context.market = market
        context.banking = banking
        context.news = news
        context.player = player
        context.allocator = allocator
        context.names = names

        # The world's other companies, restored against the reloaded market so
        # they keep trading exactly as they were (V26.2, V16.11).
        from ..ai import AICompanies

        ai = AICompanies(allocator=allocator)
        ai.restore(state.get("ai", {}), market=market, names=names,
                   rng=Random(world.seed))
        ai.register(engine)
        context.ai = ai

        # Lifetime records belong to the playthrough, so they are restored
        # rather than rebuilt (V28.7).
        from ..statistics import LifetimeStatistics

        statistics = LifetimeStatistics(config=self.config)
        statistics.restore(state.get("statistics", {}))
        context.statistics = statistics

        self._restore_analytics(state.get("analytics", {}), engine)

        self.metadata = document.metadata
        self.playtime_seconds = document.metadata.playtime_seconds
        self._seconds_since_autosave = 0.0
        self.unsaved_changes = False

    def _restore_analytics(self, data: dict, engine: SimulationEngine) -> None:
        """Rebuild analytics against the reloaded world and re-attach it."""
        from ..analytics import AnalyticsService, HistoryRecorder

        history = HistoryRecorder(self.context, config=self.config)
        history.restore(data.get("history", {}))
        history.register(engine)
        service = AnalyticsService(self.context, history=history)
        service.restore(data)
        self.context.analytics = service

    # -- saving ------------------------------------------------------------
    def save_to_slot(self, slot: str | int, name: str | None = None) -> SaveResult:
        """Write the game to a slot, reporting success or failure (V16.4)."""
        if name:
            self.metadata.name = name
        try:
            document = self.gather()
            path = self.store.write(slot, document)
        except Exception as exc:  # a failed save must not end the game
            logger.exception("Saving to slot %s failed.", slot)
            return SaveResult(False, f"Saving failed: {exc}")
        self.unsaved_changes = False
        return SaveResult(True, f"Saved to {self.store.info(slot).label}.", path)

    def autosave(self, reason: str = "") -> SaveResult:
        """Write the rolling autosave, replacing the previous one (V16.7)."""
        result = self.save_to_slot(AUTOSAVE_SLOT)
        if result.ok:
            message = "Autosaved" if not reason else f"Autosaved before {reason}"
            for callback in list(self.on_autosave):
                callback(message)
            logger.info(message)
        return result

    def autosave_before(self, decision: str) -> SaveResult:
        """Autosave immediately before a major irreversible decision (V16.6)."""
        return self.autosave(reason=decision)

    @property
    def autosave_interval_minutes(self) -> float:
        """Real minutes between autosaves; zero turns them off."""
        return self._autosave_minutes

    def set_autosave_interval(self, minutes: float) -> None:
        """Change how often the game autosaves; players may adjust this (V16.5)."""
        self._autosave_minutes = max(0.0, minutes)
        self._seconds_since_autosave = 0.0

    # -- loading -----------------------------------------------------------
    def load_from_slot(self, slot: str | int, *, allow_damaged: bool = False) -> LoadOutcome:
        """Read a slot, validating, migrating and repairing as needed (V16.13-16.15)."""
        try:
            raw = self.store.read(slot)
        except OSError as exc:
            return LoadOutcome(None, ok=False, problems=[f"That save could not be opened: {exc}"])

        outcome = read_save(raw, allow_damaged=allow_damaged)
        if outcome.ok and outcome.document is not None:
            self.apply(outcome.document)
        return outcome

    def slots(self) -> list[SlotInfo]:
        return self.store.list_slots()

    # -- export and import (V16.21, V16.22) --------------------------------
    def export_slot(self, slot: str | int, destination: Path) -> SaveResult:
        try:
            path = self.store.export(slot, Path(destination))
        except Exception as exc:
            return SaveResult(False, f"Export failed: {exc}")
        return SaveResult(True, f"Exported to {path}.", path)

    def import_slot(self, source: Path, slot: str | int) -> SaveResult:
        try:
            path = self.store.import_file(Path(source), slot)
        except Exception as exc:
            return SaveResult(False, f"Import failed: {exc}")
        return SaveResult(True, f"Imported into {self.store.info(slot).label}.", path)
