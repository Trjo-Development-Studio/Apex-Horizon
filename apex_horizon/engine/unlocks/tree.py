"""The Unlock Tree.

V6.2 makes the point this module exists to enforce: new mechanics are *earned*,
not immediately available. V6.19 asks for the tree to be a directed acyclic
graph with each unlock's prerequisites stored as explicit edges, so branches
defined later attach without changing traversal — which is exactly how it is
built here, and why V6.8's final unlock, which converges seven branches at once,
needs no special handling.

V6.4 fixes the start of the primary progression: the player **always begins with
Basic Investing**, then Create Company, then Company Level 2. Beginning with
Basic Investing is what makes the opening of the game playable — the player is
an individual investor with $10,000 (V1.19, V1.21) who can trade their own money
from the first day, and who must build enough personal wealth to afford a
company (V3.3).

The tree's contents live in :mod:`.catalogue`; this module is only the machinery
that reads them. Prices come from configuration (V15.10, and the project
manager's ruling that unlock prices stay tunable): each unlock declares how deep
it sits and its price is a multiple of the company founding cost, so one number
rescales the whole tree.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import Money

logger = get_logger(__name__)


@dataclass(frozen=True)
class Unlock:
    """One node of the tree (V6.19: prerequisites are explicit edges)."""

    key: str
    name: str
    description: str
    #: Which branch this belongs to, and where along it — used only for layout.
    branch: str = "primary"
    position: int = 0
    #: Keys that must already be unlocked. Empty for the root (V6.9).
    requires: tuple[str, ...] = ()
    #: How deep this sits, indexing `unlocks.cost_multipliers`. Prices are never
    #: written into the catalogue (V15.10).
    cost_tier: int = 0
    #: True for unlocks the player already owns when the game begins (V6.4).
    owned_at_start: bool = False
    #: False while the system this unlock gates does not exist yet. The node is
    #: still shown, because V6.14 wants the remaining tree visible as long-term
    #: ambition, but it cannot be bought: V6.3 requires an unlock to change
    #: something.
    implemented: bool = True


class UnlockTree:
    """What the player has earned, and what they may earn next."""

    def __init__(self, *, config: Config | None = None):
        from .catalogue import UNLOCKS

        self.config = config or get_config()
        self.all = UNLOCKS
        self.by_key = {unlock.key: unlock for unlock in UNLOCKS}
        self.unlocked: set[str] = {
            unlock.key for unlock in UNLOCKS if unlock.owned_at_start
        }
        #: Called with each unlock purchased, so the interface can react (V14.16).
        self.on_unlocked: list = []

    # -- access ------------------------------------------------------------
    def has(self, key: str) -> bool:
        return key in self.unlocked

    def highest(self, *keys: str) -> int:
        """How far along an ordered chain the player has reached, 0 for none.

        Branches are strictly sequential (V6.9), so counting how many of a chain
        are owned is the same as finding the furthest one reached — and it saves
        every caller writing a ladder of ``if has(...)`` for each level.
        """
        reached = 0
        for index, key in enumerate(keys, start=1):
            if key in self.unlocked:
                reached = index
        return reached

    def cost_of(self, key: str) -> Money:
        """What an unlock costs, read from configuration every time (V15.10)."""
        unlock = self.by_key.get(key)
        if unlock is None or unlock.owned_at_start:
            return Money.zero()
        multipliers = self.config.get_list("unlocks.cost_multipliers")
        if not multipliers:
            return Money.zero()
        index = max(0, min(unlock.cost_tier, len(multipliers) - 1))
        founding = Decimal(self.config.get_int("company.founding_cost"))
        return Money(founding * Decimal(str(multipliers[index])))

    def prerequisites_met(self, key: str) -> bool:
        unlock = self.by_key.get(key)
        if unlock is None:
            return False
        return all(requirement in self.unlocked for requirement in unlock.requires)

    def missing_prerequisites(self, key: str) -> list[Unlock]:
        unlock = self.by_key.get(key)
        if unlock is None:
            return []
        return [
            self.by_key[requirement] for requirement in unlock.requires
            if requirement not in self.unlocked and requirement in self.by_key
        ]

    def available(self) -> list[Unlock]:
        """Unlocks the player could buy now: prerequisites met, not yet owned.

        V6.17 requires every qualifying unlock to become available together
        rather than being staggered, so this reports all of them.
        """
        return [
            unlock for unlock in self.all
            if unlock.key not in self.unlocked
            and unlock.implemented
            and self.prerequisites_met(unlock.key)
        ]

    def branch(self, name: str) -> list[Unlock]:
        """One branch in order, for drawing it as a horizontal line (V6.10)."""
        return sorted(
            (unlock for unlock in self.all if unlock.branch == name),
            key=lambda unlock: unlock.position,
        )

    def can_purchase(self, key: str, cash: Money) -> tuple[bool, str]:
        """Whether an unlock may be bought now, and why not if not."""
        unlock = self.by_key.get(key)
        if unlock is None:
            return False, "That unlock does not exist."
        if key in self.unlocked:
            return False, f"{unlock.name} is already unlocked."
        if not unlock.implemented:
            return False, (
                f"{unlock.name} arrives with the system it opens, in a later "
                "version of the game."
            )
        if not self.prerequisites_met(key):
            missing = [item.name for item in self.missing_prerequisites(key)]
            # V6.9: progression cannot be skipped.
            return False, f"{unlock.name} requires {' and '.join(missing)} first."
        cost = self.cost_of(key)
        if cash < cost:
            return False, (
                f"{unlock.name} costs {cost.format(decimals=0)}; "
                f"you have {cash.format(decimals=0)}."
            )
        return True, ""

    def unlock(self, key: str) -> None:
        """Grant an unlock. Paying for it is the caller's responsibility."""
        if key in self.unlocked:
            return
        self.unlocked.add(key)
        unlock = self.by_key.get(key)
        logger.info("Unlocked %s.", unlock.name if unlock else key)
        for callback in list(self.on_unlocked):
            callback(unlock)

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {"unlocked": sorted(self.unlocked)}

    def restore(self, data: dict) -> None:
        # Keys the catalogue no longer has are dropped rather than carried
        # forward (V16.15): an unlock removed from the tree — the structural
        # "Employees" root, removed 2026-08-11 — must not go on counting
        # towards "N of M unlocked" in a save written before it went.
        self.unlocked = {
            key for key in data.get("unlocked", []) if key in self.by_key
        }
        # An unlock every player starts with is never absent, even from a save
        # written before it existed (V16.15).
        self.unlocked.update(
            unlock.key for unlock in self.all if unlock.owned_at_start
        )
