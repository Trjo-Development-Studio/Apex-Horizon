"""The command table itself: registration, dispatch, help and scheduling.

The command *implementations* live in sibling modules and are mixed in below,
so this file stays about how a typed line becomes a reply rather than about
what any particular command does (split 2026-08-10, for file size).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from ...engine.config import Config, get_config
from ...engine.values import get_calendar
from .base import TOPICS, Command, Reply, logger, no
from .money import MoneyCommands
from .time_travel import TimeCommands
from .unlocks import UnlockCommands
from .world import WorldCommands


class DeveloperCommands(MoneyCommands, TimeCommands, UnlockCommands,
                        WorldCommands):
    """The command set, operating directly on a running game."""

    def __init__(self, context, app=None, *, config: Config | None = None):
        self.context = context
        self.app = app
        self.config = config or get_config()
        self.commands: dict[str, Command] = {}
        #: In-game days still to be simulated by :meth:`pump`.
        self.pending_days = 0
        #: Called with lines produced after a command has already returned.
        self.on_output: list[Callable[[str], None]] = []
        self._max_fast_forward_years = self.config.get_int("debug.max_fast_forward_years")
        self._register_all()

    # -- running -----------------------------------------------------------
    def execute(self, line: str) -> Reply:
        """Run one command line and return what to show. Never raises."""
        parts = line.split()
        if not parts:
            return Reply("")
        name, arguments = parts[0].lower(), parts[1:]
        command = self.commands.get(name)
        if command is None:
            return no(f"Unknown command: {name}. Use 'help' for available commands.")
        try:
            answer = command.run(*arguments)
        except TypeError:
            return no(f"Usage: {command.usage}")
        except Exception as error:  # a typo must never end the game (V15.18)
            logger.exception("Debug command %r failed.", line)
            return no(f"{name} failed: {error}")
        return answer if isinstance(answer, Reply) else Reply(answer)

    def changed(self) -> None:
        """Note that the world now differs from what was last saved (V16.23).

        A command is a real change to the game, so the save indicator should
        say so; a console that quietly left it reading "all changes saved"
        would be lying about the one thing that indicator is for.
        """
        saves = getattr(self.context, "saves", None)
        if saves is not None:
            saves.mark_changed()

    def emit(self, message: str) -> None:
        """Report something that happened after a command returned."""
        for callback in list(self.on_output):
            callback(message)

    # -- scheduled time (see the module docstring) -------------------------
    @property
    def busy(self) -> bool:
        return self.pending_days > 0

    def pump(self, budget_seconds: float) -> None:
        """Simulate as much of a scheduled jump as fits in ``budget_seconds``."""
        if self.pending_days <= 0:
            return
        engine = self.context.engine
        if engine is None:  # the world went away underneath us
            self.pending_days = 0
            return
        deadline = time.perf_counter() + max(0.0, budget_seconds)
        while self.pending_days > 0 and time.perf_counter() < deadline:
            engine.run_days(1)
            self.pending_days -= 1
        self.changed()
        if self.pending_days == 0:
            self.emit(f"Time is now {engine.date.label()}.")

    def _schedule(self, days: int) -> str:
        years = self._max_fast_forward_years
        limit = years * get_calendar().days_per_year
        if limit > 0 and days > limit:
            return no(
                f"That is {days:,} days. The console simulates at most {years} "
                f"years ({limit:,} days) per command, so the window keeps drawing."
            )
        self.pending_days += days
        return (
            f"Simulating {days:,} in-game day(s). "
            "The game keeps running while it catches up."
        )

    # -- the table ---------------------------------------------------------
    def _add(self, name: str, summary: str, syntax, run) -> None:
        self.commands[name] = Command(name, summary, tuple(syntax), run)

    def _register_all(self) -> None:
        self._add("help", "List the commands, or explain one topic.", (
            ("help", "Every command."),
            ("help money", "Money commands only."),
            ("help time", "Time commands only."),
            ("help unlocks", "Unlock commands only."),
        ), self._help)

        self._add("money", "Read or change personal and company money.", (
            ("money player", "Show the player's personal cash."),
            ("money player set {amount}", "Set personal cash to {amount}."),
            ("money player add {amount}", "Add {amount} to personal cash."),
            ("money player remove {amount}", "Take {amount} from personal cash."),
            ("money company", "Show the company's cash."),
            ("money company set {amount}", "Set company cash to {amount}."),
            ("money company add {amount}", "Add {amount} to company cash."),
            ("money company remove {amount}", "Take {amount} from company cash."),
        ), self._money)

        self._add("time", "Read or move in-game time.", (
            ("time", "Show the current Year / Month / Week / Day."),
            ("time set {year} {month} {week} {day}", "Move time to that date."),
            ("time add {amount}{unit}",
             "Add time; unit is year, month, week or day (e.g. 'time add 5year')."),
            ("time cancel", "Abandon a jump that is still catching up."),
        ), self._time)

        self._add("unlocks", "Show what the player has unlocked.", (
            ("unlocks", "List every unlock currently purchased."),
        ), self._unlocks)

        self._add("unlock", "Grant or withdraw an unlock.", (
            ("unlock add {unlock_name}", "Unlock it, with anything it requires."),
            ("unlock remove {unlock_name}", "Remove it, and anything that needs it."),
            ("unlock add all", "Grant every unlock at once."),
        ), self._unlock)

        # The rest of what V15.18 names: employees, research, market events and
        # the economy, plus a summary of where the game stands.
        self._add("hire", "Hire applicants into the company.", (
            ("hire", "Hire one applicant."),
            ("hire {count}", "Hire up to {count} applicants."),
        ), self._hire)
        self._add("research", "Complete outstanding research at once.", (
            ("research", "Bring every pending opportunity forward to today."),
        ), self._research)
        self._add("event", "Trigger a market event moving every price.", (
            ("event {up|down}", "Move every listed price by 5%."),
            ("event {up|down} {percent}", "Move every listed price by {percent}."),
        ), self._event)
        self._add("economy", "Set economic health.", (
            ("economy {health}", "Set economic health, -1 (worst) to 1 (best)."),
        ), self._economy)
        self._add("status", "Print where the game currently stands.", (
            ("status", "Date, cash, economy, market and company at a glance."),
        ), self._status)

    # -- help --------------------------------------------------------------
    def _help(self, topic: str = "") -> str:
        if not topic:
            lines = ["Developer commands. 'help {topic}' explains one in full."]
            width = max(len(command.usage) for command in self.commands.values())
            for command in self._ordered():
                lines.append(f"  {command.usage.ljust(width)}   {command.summary}")
            lines.append("Topics: " + ", ".join(sorted(TOPICS)))
            return "\n".join(lines)

        names = TOPICS.get(topic.lower())
        if names is None:
            command = self.commands.get(topic.lower())
            names = (command.name,) if command else None
        if names is None:
            return no(f"No help for {topic}. Topics: " + ", ".join(sorted(TOPICS)))

        lines = []
        for name in names:
            command = self.commands[name]
            width = max(len(line) for line, _ in command.syntax)
            lines.append(f"{command.name} — {command.summary}")
            lines += [
                f"  {line.ljust(width)}   {what}" for line, what in command.syntax
            ]
        return "\n".join(lines)

    def _ordered(self) -> list[Command]:
        """Commands in the order the specification introduces them."""
        first = ["money", "time", "unlocks", "unlock", "help"]
        rest = sorted(name for name in self.commands if name not in first)
        return [self.commands[name] for name in first + rest]
