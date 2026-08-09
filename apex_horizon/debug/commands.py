"""Developer commands, and what they do to the running game.

V15.18 asks for a developer console covering money, time, employees, research,
market events and the economy. This module is the commands themselves, with no
opinion about where they were typed: the terminal reader in :mod:`.console` and
the in-game overlay in :mod:`..ui.console` both drive this one object, so there
is a single definition of what every command means and a single help text
describing it.

Two rules shape everything here.

**Commands act on the real systems.** ``money player add 1000`` moves the same
cash the market spends, the interface draws and the save writes; ``time add
1year`` runs the simulation through every one of those days rather than moving a
label. Where a legitimate game API exists it is used (V15.28) — company money
arrives as owner capital through the company's own transfer method, so the
ledger and cash-flow statement stay truthful. What a command deliberately skips
is the *price*: that is the point of a debug tool.

**Nothing typed can end the game.** Every command validates its own arguments
and returns a sentence; the caller only prints it.

Time is the exception to running immediately. A year takes several seconds to
simulate honestly, so ``time add 5year`` would freeze the window for half a
minute if it ran inside one command. Instead the command schedules the days and
:meth:`DeveloperCommands.pump` advances them a slice at a time, once per frame,
leaving the game drawing and responsive while the world catches up.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..engine.config import Config, get_config
from ..engine.logging_setup import get_logger
from ..engine.values import Money, get_calendar

logger = get_logger(__name__)

#: Accepted forms of ``time add 5year``. One unit per command, as specified.
TIME_ADD = re.compile(r"^(\d+)\s*(year|month|week|day)s?$")

INVALID = "Invalid syntax. Use 'help' for available commands."


class Reply(str):
    """What a command returned, and whether it worked.

    A console has to show a refusal differently from an answer, and guessing
    from the wording would be exactly that — a guess. This is an ordinary string
    everywhere else, printed and compared and searched as before, that
    additionally remembers whether the command it came from succeeded.
    """

    ok: bool

    def __new__(cls, text: str, ok: bool = True) -> Reply:
        reply = super().__new__(cls, text)
        reply.ok = ok
        return reply


def no(text: str) -> Reply:
    """A refusal: correct behaviour, but not what was asked for."""
    return Reply(text, ok=False)


@dataclass(frozen=True)
class Command:
    """One developer command, and the exact syntax its help shows."""

    name: str
    summary: str
    #: Each entry is one exact command line and what it does.
    syntax: tuple[tuple[str, str], ...]
    run: Callable[..., str]

    @property
    def usage(self) -> str:
        return self.syntax[0][0] if self.syntax else self.name


#: Which commands each help topic covers.
TOPICS = {
    "money": ("money",),
    "time": ("time",),
    "unlocks": ("unlocks", "unlock"),
}


class DeveloperCommands:
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

    # -- money -------------------------------------------------------------
    def _money(self, *args: str) -> str:
        if not args:
            return no("Invalid syntax. Use 'help money' for the exact syntax.")
        target = args[0].lower()
        if target == "player":
            return self._money_player(args[1:])
        if target == "company":
            return self._money_company(args[1:])
        return no(f"Unknown target: {args[0]}. Use 'money player' or 'money company'.")

    def _money_player(self, args: tuple[str, ...]) -> str:
        player = self.context.player
        if player is None:
            return no("No game is running.")
        if not args:
            return f"Personal cash: {player.cash.format()}."
        action, amount, problem = self._money_arguments(args, "player")
        if amount is None:
            return problem or no(INVALID)
        before = player.cash
        if action == "set":
            player.cash = amount
        elif action == "add":
            player.cash = before + amount
        else:
            player.cash = before - amount
        self.changed()
        return (
            f"Personal cash: {player.cash.format()} "
            f"(was {before.format()})."
        )

    def _money_company(self, args: tuple[str, ...]) -> str:
        company = self.context.company
        if company is None:
            return no("No company currently exists.")
        finances = company.finances
        if not args:
            return f"{company.name} cash: {finances.cash.format()}."
        action, amount, problem = self._money_arguments(args, "company")
        if amount is None:
            return problem or no(INVALID)
        before = finances.cash
        if action == "set":
            amount = amount - before
            action = "add" if not amount.is_negative else "remove"
            amount = amount if not amount.is_negative else Money(-amount.amount)
        if amount.is_zero:
            return f"{company.name} cash is already {before.format()}."

        # Company money moves through the company's own books, so the ledger and
        # cash-flow statement stay honest about where it came from (V17.26).
        day = self.context.engine.date.day
        if action == "add":
            company.receive_capital(day, amount)
        else:
            from ..engine.company.ledger import ExpenseCategory

            finances.repay_financing(day, ExpenseCategory.OTHER, amount,
                                     "Developer console withdrawal")
        self.changed()
        return (
            f"{company.name} cash: {finances.cash.format()} "
            f"(was {before.format()})."
        )

    def _money_arguments(
        self, args: tuple[str, ...], target: str
    ) -> tuple[str, Money | None, str]:
        """Validate ``set|add|remove {amount}``, returning what to do or why not."""
        action = args[0].lower()
        if action not in ("set", "add", "remove"):
            return "", None, no(
                f"Unknown action: {args[0]}. Use set, add or remove — "
                f"'help money' shows the exact syntax."
            )
        if len(args) != 2:
            return "", None, no(
                f"Invalid syntax. Use 'money {target} {action} {{amount}}'.")
        amount, problem = _parse_amount(args[1])
        if amount is None:
            return "", None, problem
        if action != "set" and amount.is_negative:
            other = "remove" if action == "add" else "add"
            return "", None, no(
                f"Amounts cannot be negative. Use 'money {target} {other}' instead."
            )
        return action, amount, ""

    # -- time --------------------------------------------------------------
    def _time(self, *args: str) -> str:
        engine = self.context.engine
        if engine is None:
            return no("No game is running.")
        if not args:
            now = f"It is {engine.date.label()}."
            return f"{now} Simulating {self.pending_days:,} more day(s)." \
                if self.busy else now

        action = args[0].lower()
        if action == "set":
            return self._time_set(args[1:])
        if action == "add":
            return self._time_add(args[1:])
        if action == "cancel":
            if not self.busy:
                return no("No time jump is running.")
            abandoned, self.pending_days = self.pending_days, 0
            return f"Abandoned {abandoned:,} remaining day(s) at {engine.date.label()}."
        return no("Invalid syntax. Use 'help time' for the exact syntax.")

    def _time_set(self, args: tuple[str, ...]) -> str:
        if len(args) != 4:
            return no("Invalid syntax. Use 'time set {year} {month} {week} {day}'.")
        calendar = get_calendar()
        limits = (
            ("year", None),
            ("month", calendar.months_per_year),
            ("week", calendar.weeks_per_month),
            ("day", calendar.days_per_week),
        )
        values = []
        for text, (label, highest) in zip(args, limits, strict=True):
            try:
                value = int(text)
            except ValueError:
                return no(f"{text} is not a whole number of {label}s.")
            if value < 1:
                return no(f"The {label} must be 1 or greater.")
            if highest is not None and value > highest:
                return no(f"The {label} must be between 1 and {highest}.")
            values.append(value)

        year, month, week, day = values
        target = (
            (year - 1) * calendar.days_per_year
            + (month - 1) * calendar.days_per_month
            + (week - 1) * calendar.days_per_week
            + day
        )
        engine = self.context.engine
        current = engine.date.day + self.pending_days
        if target == current:
            return f"It is already {engine.date.label()}."
        if target < current:
            # The simulation only knows how to live days, not to unlive them.
            return no(
                f"Time only moves forwards. It is already {engine.date.label()}; "
                "start a new game to go back."
            )
        return self._schedule(target - current)

    def _time_add(self, args: tuple[str, ...]) -> str:
        match = TIME_ADD.match("".join(args).lower())
        if match is None:
            return no(
                "Invalid syntax. Use 'time add {amount}{unit}', where unit is "
                "year, month, week or day — for example 'time add 5year'."
            )
        amount, unit = int(match.group(1)), match.group(2)
        if amount < 1:
            return no("Add at least one day.")
        calendar = get_calendar()
        per_unit = {
            "year": calendar.days_per_year,
            "month": calendar.days_per_month,
            "week": calendar.days_per_week,
            "day": 1,
        }[unit]
        return self._schedule(amount * per_unit)

    # -- unlocks -----------------------------------------------------------
    def _unlocks(self, *args: str) -> str:
        if args:
            return no("Invalid syntax. Use 'unlocks' on its own.")
        tree = self.context.unlocks
        if tree is None:
            return no("No game is running.")
        owned = [unlock for unlock in tree.all if tree.has(unlock.key)]
        if not owned:
            return "Nothing is unlocked."
        lines = [f"Unlocked ({len(owned)} of {len(tree.all)}):"]
        width = max(len(unlock.key) for unlock in owned)
        lines += [f"  {unlock.key.ljust(width)}   {unlock.name}" for unlock in owned]
        return "\n".join(lines)

    def _unlock(self, *args: str) -> str:
        tree = self.context.unlocks
        if tree is None:
            return no("No game is running.")
        if not args or args[0].lower() not in ("add", "remove"):
            return no("Invalid syntax. Use 'help unlocks' for the exact syntax.")
        action, name = args[0].lower(), " ".join(args[1:])
        if not name:
            return no(f"Invalid syntax. Use 'unlock {action} {{unlock_name}}'.")
        if action == "add" and name.lower() == "all":
            for unlock in tree.all:
                if unlock.implemented:
                    tree.unlock(unlock.key)
            self._apply_effects()
            self.changed()
            return f"Granted every unlock ({len(tree.unlocked)} of {len(tree.all)})."

        key = _resolve_unlock(tree, name)
        if key is None:
            return no(f"Unknown unlock: {name}")
        return self._unlock_add(tree, key) if action == "add" \
            else self._unlock_remove(tree, key)

    def _unlock_add(self, tree, key: str) -> str:
        unlock = tree.by_key[key]
        if tree.has(key):
            return no(f"{unlock.name} is already unlocked.")
        if not unlock.implemented:
            return no(
                f"{unlock.name} arrives with the system it opens, in a later "
                "version of the game."
            )
        # V6.9 makes progression sequential, so granting a deep unlock without
        # what it requires would leave the tree in a state the game never
        # produces. Grant the chain instead, and say so.
        needed = _prerequisite_chain(tree, key)
        for requirement in needed:
            tree.unlock(requirement)
        tree.unlock(key)
        self._apply_effects()
        self.changed()
        if not needed:
            return f"Unlocked {unlock.name}."
        also = ", ".join(tree.by_key[requirement].name for requirement in needed)
        return f"Unlocked {unlock.name}, and what it required: {also}."

    def _unlock_remove(self, tree, key: str) -> str:
        unlock = tree.by_key[key]
        if unlock.owned_at_start:
            return no(
                f"{unlock.name} is granted to every player at the start (V6.4) "
                "and cannot be removed."
            )
        if not tree.has(key):
            return no(f"{unlock.name} is not unlocked.")
        # Removing a prerequisite would strand everything built on top of it, so
        # those come out too rather than leaving an impossible tree behind.
        dependents = _dependent_chain(tree, key)
        for dependent in dependents:
            tree.unlocked.discard(dependent)
        tree.unlocked.discard(key)
        self._apply_effects()
        self.changed()
        if not dependents:
            return f"Removed {unlock.name}."
        also = ", ".join(tree.by_key[dependent].name for dependent in dependents)
        return f"Removed {unlock.name}, and what depended on it: {also}."

    def _apply_effects(self) -> None:
        """Push the tree's consequences back into the systems it configures."""
        effects = getattr(self.app, "effects", None)
        if effects is None:
            from ..engine.unlocks import UnlockEffects

            effects = UnlockEffects(self.context.unlocks)
        effects.apply(self.context)

    # -- the rest of V15.18 ------------------------------------------------
    def _hire(self, count: str = "1") -> str:
        company = self.context.company
        if company is None:
            return no("No company currently exists.")
        roster = company.employees
        engine = self.context.engine
        roster.refresh_applicants(engine.rng, self.context.names,
                                  self.context.allocator, engine.date.day)
        hired = 0
        for applicant in list(roster.applicants)[: int(count)]:
            if roster.hire(applicant, engine.date.day)[0]:
                hired += 1
        self.changed()
        return f"Hired {hired}; the company now employs {len(roster)}."

    def _research(self) -> str:
        """Finish what research has found, so it can be acted on at once."""
        company = self.context.company
        system = getattr(company, "investments", None) if company else None
        if system is None:
            return no("No company currently exists.")
        moved = 0
        for opportunity in list(system.opportunities):
            if getattr(opportunity, "ready_on_day", None) is not None:
                opportunity.ready_on_day = self.context.engine.date.day
                moved += 1
        self.changed()
        return f"Brought {moved} opportunit(y/ies) forward."

    def _event(self, direction: str = "up", percent: str = "5") -> str:
        """Move every listed price at once (V15.18: trigger market events)."""
        market = self.context.market
        if market is None:
            return no("No game is running.")
        if direction.lower() not in ("up", "down"):
            return no("Direction must be 'up' or 'down'.")
        size = Decimal(str(float(percent) / 100))
        if direction.lower() == "down":
            size = -size
        listings = market.active_listings()
        for listing in listings:
            listing.price = Money(listing.price.amount * (Decimal(1) + size))
        self.changed()
        return f"Moved {len(listings)} listings by {float(size):+.1%}."

    def _economy(self, health: str) -> str:
        economy = self.context.economy
        if economy is None:
            return no("No game is running.")
        economy.health = max(-1.0, min(1.0, float(health)))
        self.changed()
        return f"Economy health set to {economy.health:+.2f} ({economy.state})."

    def _status(self) -> str:
        context = self.context
        if context.engine is None:
            return no("No game is running.")
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
        if self.busy:
            lines.append(f"Simulating {self.pending_days:,} more day(s).")
        return "\n".join(lines)


# -- parsing helpers --------------------------------------------------------
def _parse_amount(text: str) -> tuple[Money | None, str]:
    # The refusal is a Reply so the console can colour it as one.
    """Read a money amount as a player would type it, decimals included."""
    cleaned = text.replace("$", "").replace(",", "").replace("_", "").strip()
    try:
        value = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None, no(_NOT_AN_AMOUNT.format(text=text))
    if not value.is_finite():
        return None, no(_NOT_AN_AMOUNT.format(text=text))
    return Money(value), ""


_NOT_AN_AMOUNT = "{text} is not an amount. Try a number, such as 1000 or 12.50."


def _normalise(name: str) -> str:
    """One spelling for 'Create Company', 'create_company' and 'create-company'."""
    return re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")


def _resolve_unlock(tree, name: str) -> str | None:
    """Find an unlock by key or by the name shown in the interface."""
    wanted = _normalise(name)
    for unlock in tree.all:
        if _normalise(unlock.key) == wanted or _normalise(unlock.name) == wanted:
            return unlock.key
    return None


def _prerequisite_chain(tree, key: str) -> list[str]:
    """Everything ``key`` needs that is not unlocked yet, deepest first."""
    ordered: list[str] = []
    seen: set[str] = set()

    def walk(current: str) -> None:
        for requirement in tree.by_key[current].requires:
            if requirement in seen or requirement not in tree.by_key:
                continue
            seen.add(requirement)
            walk(requirement)
            if not tree.has(requirement):
                ordered.append(requirement)

    walk(key)
    return ordered


def _dependent_chain(tree, key: str) -> list[str]:
    """Every unlocked node that would be stranded by removing ``key``."""
    stranded: list[str] = []
    frontier = {key}
    while frontier:
        following = set()
        for unlock in tree.all:
            if unlock.key in stranded or unlock.key == key:
                continue
            if not tree.has(unlock.key):
                continue
            if frontier.isdisjoint(unlock.requires):
                continue
            stranded.append(unlock.key)
            following.add(unlock.key)
        frontier = following
    return stranded
