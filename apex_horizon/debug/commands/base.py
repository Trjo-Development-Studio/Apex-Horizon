"""The pieces every developer command is built from.

Split out of the single commands module (2026-08-10) to keep each file within
the size the project works to. Everything here is independent of the running
game: the reply types, the command table's own record, and the small parsers
the command groups share. Nothing here imports a command group, which is what
keeps the package's imports acyclic.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ...engine.logging_setup import get_logger
from ...engine.values import Money

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
