"""The Unlock Tree.

V6.2 makes the point this module exists to enforce: new mechanics are *earned*,
not immediately available. V6.19 asks for the tree to be a directed acyclic
graph with each unlock's prerequisites stored as explicit edges, so branches
defined later attach without changing traversal — which is exactly how it is
built here.

V6.4 fixes the start of the primary progression: the player **always begins with
Basic Investing**, then Create Company, then Company Level 2. Beginning with
Basic Investing is what makes the opening of the game playable — the player is
an individual investor with $10,000 (V1.19, V1.21) who can trade their own money
from the first day, and who must build enough personal wealth to afford a
company (V3.3).

Only the part of the tree whose effects are actually wired is defined here.
Selling the player an unlock that changes nothing would break V6.3, which
requires every unlock to provide a noticeable improvement or a new system. The
remaining branches arrive with the systems they gate.

Costs live in configuration, never in this file (V15.10, and the project
manager's ruling that unlock prices must stay tunable).
"""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import Money

logger = get_logger(__name__)

#: Identifiers for the unlocks whose effects exist today (V6.5).
BASIC_INVESTING = "basic_investing"
CREATE_COMPANY = "create_company"


@dataclass(frozen=True)
class Unlock:
    """One node of the tree (V6.19: prerequisites are explicit edges)."""

    key: str
    name: str
    description: str
    #: Keys that must already be unlocked. Empty for the root (V6.9).
    requires: tuple[str, ...] = ()
    #: Config key holding this unlock's price, so it stays tunable (V15.10).
    cost_key: str = ""
    #: True for unlocks the player already owns when the game begins (V6.4).
    owned_at_start: bool = False


#: The primary progression, as far as its effects are implemented (V6.5).
UNLOCKS: tuple[Unlock, ...] = (
    Unlock(
        key=BASIC_INVESTING,
        name="Basic Investing",
        description="Trade shares with your own money. Every player starts with this.",
        owned_at_start=True,
    ),
    Unlock(
        key=CREATE_COMPANY,
        name="Create Company",
        description="Permission to found a company. Founding it costs extra.",
        requires=(BASIC_INVESTING,),
        cost_key="unlocks.create_company_cost",
    ),
)

BY_KEY: dict[str, Unlock] = {unlock.key: unlock for unlock in UNLOCKS}


class UnlockTree:
    """What the player has earned, and what they may earn next."""

    def __init__(self, *, config: Config | None = None):
        self.config = config or get_config()
        self.unlocked: set[str] = {
            unlock.key for unlock in UNLOCKS if unlock.owned_at_start
        }
        #: Called with each unlock purchased, so the interface can react (V14.16).
        self.on_unlocked: list = []

    # -- access ------------------------------------------------------------
    def has(self, key: str) -> bool:
        return key in self.unlocked

    def cost_of(self, key: str) -> Money:
        """What an unlock costs, read from configuration every time (V15.10)."""
        unlock = BY_KEY.get(key)
        if unlock is None or not unlock.cost_key:
            return Money.zero()
        return Money(self.config.get_int(unlock.cost_key))

    def prerequisites_met(self, key: str) -> bool:
        unlock = BY_KEY.get(key)
        if unlock is None:
            return False
        return all(requirement in self.unlocked for requirement in unlock.requires)

    def available(self) -> list[Unlock]:
        """Unlocks the player could buy now: prerequisites met, not yet owned.

        V6.17 requires every qualifying unlock to become available together
        rather than being staggered, so this reports all of them.
        """
        return [
            unlock for unlock in UNLOCKS
            if unlock.key not in self.unlocked and self.prerequisites_met(unlock.key)
        ]

    def can_purchase(self, key: str, cash: Money) -> tuple[bool, str]:
        """Whether an unlock may be bought now, and why not if not."""
        unlock = BY_KEY.get(key)
        if unlock is None:
            return False, "That unlock does not exist."
        if key in self.unlocked:
            return False, f"{unlock.name} is already unlocked."
        if not self.prerequisites_met(key):
            missing = [
                BY_KEY[requirement].name for requirement in unlock.requires
                if requirement not in self.unlocked
            ]
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
        unlock = BY_KEY.get(key)
        logger.info("Unlocked %s.", unlock.name if unlock else key)
        for callback in list(self.on_unlocked):
            callback(unlock)

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {"unlocked": sorted(self.unlocked)}

    def restore(self, data: dict) -> None:
        self.unlocked = set(data.get("unlocked", []))
        # An unlock every player starts with is never absent, even from a save
        # written before it existed (V16.15).
        self.unlocked.update(
            unlock.key for unlock in UNLOCKS if unlock.owned_at_start
        )
