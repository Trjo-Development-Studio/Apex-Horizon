"""Developer commands typed into the terminal that launched the game.

V15.18 asks for exactly this instead of an in-game developer menu: commands run
from the terminal, covering money, time, employees, research, market events and
the economy. The terminal is the primary debugging interface.

Reading a line from a terminal blocks until someone presses return, which would
freeze the simulation, so a daemon thread does the reading and puts whole lines
on a queue. The application drains that queue once a frame and runs the commands
on its own thread — so a command never mutates the world underneath a frame that
is halfway through drawing it.

The console is inert wherever there is no terminal to read: tests, CI, and a
windowed launch with no console all leave stdin unusable, and it simply does not
start. It is a development tool and says so on the first line it prints.
"""

from __future__ import annotations

import queue
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

from ..engine.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class Command:
    """One developer command."""

    name: str
    usage: str
    summary: str
    run: Callable[..., str]


class DebugConsole:
    """Reads developer commands from the launching terminal (V15.18)."""

    def __init__(self, context, app=None):
        self.context = context
        self.app = app
        self.commands: dict[str, Command] = {}
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._register_all()

    # -- lifecycle ---------------------------------------------------------
    @property
    def available(self) -> bool:
        """Whether there is a terminal to read commands from."""
        try:
            return bool(sys.stdin) and sys.stdin.isatty()
        except (AttributeError, ValueError):
            return False

    def start(self) -> bool:
        """Begin reading, if a terminal is attached. Safe to call always."""
        if self._running or not self.available:
            return False
        self._running = True
        self._thread = threading.Thread(target=self._read_lines, daemon=True,
                                        name="apex-debug-console")
        self._thread.start()
        print("Apex Horizon developer console (V15.18). Type 'help' for commands.",
              flush=True)
        return True

    def stop(self) -> None:
        self._running = False

    def _read_lines(self) -> None:
        """Block on the terminal, off the main thread."""
        while self._running:
            try:
                line = sys.stdin.readline()
            except (OSError, ValueError):
                break
            if not line:
                break
            self._queue.put(line.strip())

    # -- running -----------------------------------------------------------
    def poll(self) -> None:
        """Run whatever has been typed. Called once a frame by the app."""
        while True:
            try:
                line = self._queue.get_nowait()
            except queue.Empty:
                return
            if line:
                print(self.execute(line), flush=True)

    def execute(self, line: str) -> str:
        """Run one command line and return what to print."""
        parts = line.split()
        if not parts:
            return ""
        name, arguments = parts[0].lower(), parts[1:]
        command = self.commands.get(name)
        if command is None:
            return f"Unknown command {name!r}. Type 'help' for the list."
        try:
            return command.run(*arguments)
        except TypeError:
            return f"Usage: {command.usage}"
        except Exception as error:  # a bad command must never end the game
            logger.exception("Debug command %r failed.", line)
            return f"{name} failed: {error}"

    # -- the commands (V15.18) ---------------------------------------------
    def _add(self, name: str, usage: str, summary: str, run) -> None:
        self.commands[name] = Command(name, usage, summary, run)

    def _register_all(self) -> None:
        self._add("help", "help", "List the commands.", self._help)
        self._add("money", "money <amount>", "Give the player personal cash.",
                  self._money)
        self._add("company", "company <amount>", "Give the company cash.",
                  self._company_money)
        self._add("days", "days <count>", "Advance time by whole days.", self._days)
        self._add("hire", "hire [count]", "Spawn employees into the company.",
                  self._hire)
        self._add("research", "research", "Complete outstanding research at once.",
                  self._research)
        self._add("event", "event <up|down> [percent]",
                  "Trigger a market event moving every price.", self._event)
        self._add("economy", "economy <health>",
                  "Set economic health, -1 to 1.", self._economy)
        self._add("unlock", "unlock <key|all>", "Grant unlocks.", self._unlock)
        self._add("status", "status", "Print where the game currently stands.",
                  self._status)

    def _help(self) -> str:
        width = max(len(command.usage) for command in self.commands.values())
        lines = ["Developer commands (V15.18):"]
        lines += [
            f"  {command.usage.ljust(width)}  {command.summary}"
            for command in sorted(self.commands.values(), key=lambda c: c.name)
        ]
        return "\n".join(lines)

    def _money(self, amount: str) -> str:
        from ..engine.values import Money

        player = self.context.player
        player.cash = player.cash + Money(amount)
        return f"Personal cash is now {player.cash.format(decimals=0)}."

    def _company_money(self, amount: str) -> str:
        from ..engine.values import Money

        company = self.context.company
        if company is None:
            return "There is no company yet."
        company.finances.receive_capital(self.context.engine.date.day, Money(amount))
        return f"Company cash is now {company.finances.cash.format(decimals=0)}."

    def _days(self, count: str = "1") -> str:
        days = int(count)
        if days <= 0:
            return "Give a positive number of days."
        self.context.engine.run_days(days)
        return f"Advanced {days} day(s); it is now {self.context.engine.date.label()}."

    def _hire(self, count: str = "1") -> str:
        company = self.context.company
        if company is None:
            return "There is no company yet."
        roster = company.employees
        engine = self.context.engine
        roster.refresh_applicants(engine.rng, self.context.names,
                                  self.context.allocator, engine.date.day)
        hired = 0
        for applicant in list(roster.applicants)[: int(count)]:
            if roster.hire(applicant, engine.date.day)[0]:
                hired += 1
        return f"Hired {hired}; the company now employs {len(roster)}."

    def _research(self) -> str:
        """Finish what research has found, so it can be acted on at once."""
        company = self.context.company
        system = getattr(company, "investments", None) if company else None
        if system is None:
            return "There is no company investing yet."
        moved = 0
        for opportunity in list(system.opportunities):
            if getattr(opportunity, "ready_on_day", None) is not None:
                opportunity.ready_on_day = self.context.engine.date.day
                moved += 1
        return f"Brought {moved} opportunit(y/ies) forward."

    def _event(self, direction: str = "up", percent: str = "5") -> str:
        """Move every listed price at once (V15.18: trigger market events)."""
        from decimal import Decimal

        from ..engine.values import Money

        market = self.context.market
        size = Decimal(str(float(percent) / 100))
        if direction.lower() not in {"up", "down"}:
            return "Direction must be 'up' or 'down'."
        if direction.lower() == "down":
            size = -size
        listings = market.active_listings()
        for listing in listings:
            listing.price = Money(listing.price.amount * (Decimal(1) + size))
        return f"Moved {len(listings)} listings by {float(size):+.1%}."

    def _economy(self, health: str) -> str:
        economy = self.context.economy
        economy.health = max(-1.0, min(1.0, float(health)))
        return f"Economy health set to {economy.health:+.2f} ({economy.state})."

    def _unlock(self, key: str) -> str:
        tree = self.context.unlocks
        if key.lower() == "all":
            for unlock in tree.all:
                tree.unlock(unlock.key)
            granted = "every unlock"
        elif key in tree.by_key:
            tree.unlock(key)
            granted = tree.by_key[key].name
        else:
            return f"No unlock called {key!r}."
        if self.app is not None and getattr(self.app, "effects", None) is not None:
            self.app.effects.apply(self.context)
        return f"Granted {granted}."

    def _status(self) -> str:
        context = self.context
        company = context.company
        lines = [
            f"Day {context.engine.date.day} ({context.engine.date.label()})",
            f"Personal cash {context.player.cash.format(decimals=0)}, "
            f"net worth {context.player.net_worth().format(decimals=0)}",
            f"Economy {context.economy.state}, market index "
            f"{context.market.market_index():,.0f}",
        ]
        if company is not None:
            lines.append(
                f"{company.name}: level {company.level}, "
                f"cash {company.finances.cash.format(decimals=0)}, "
                f"{len(company.employees)} employees"
            )
        else:
            lines.append("No company founded yet.")
        return "\n".join(lines)
