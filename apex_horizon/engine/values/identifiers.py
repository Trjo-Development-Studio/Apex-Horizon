"""Entity identifiers.

Design Bible V30.6 requires every persistent entity — companies, employees,
investments, subsidiaries, investment funds, and saves themselves — to receive a
unique internal identifier at creation, kept distinct from its display name, so
entities can be renamed, referenced, and cross-linked without ambiguity.

Identifiers are allocated from a simple per-kind counter rather than randomly.
That keeps world generation reproducible: replaying the same generation steps
produces the same identifiers, which supports the Deterministic Simulation
guarantee in V15.11. The allocator's counters are part of the saved state, so
identifiers never collide after a save is reloaded.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

# Width of the numeric portion, chosen so identifiers sort naturally as text.
ID_NUMBER_WIDTH = 6


class EntityKind:
    """Identifier prefixes for the persistent entities named in V30.6."""

    COMPANY = "company"
    EMPLOYEE = "employee"
    INVESTMENT = "investment"
    SUBSIDIARY = "subsidiary"
    FUND = "fund"
    BANK = "bank"
    CEO = "ceo"
    CITY = "city"
    NEWS = "news"
    OPPORTUNITY = "opportunity"
    LOAN = "loan"


@dataclass
class IdAllocator:
    """Allocates sequential, unique identifiers per entity kind.

    One allocator belongs to one world (one save), so identifier sequences are
    independent between saves, consistent with the Independent Worlds principle
    in V16.12.
    """

    counters: dict[str, int] = field(default_factory=dict)

    def next_id(self, kind: str) -> str:
        """Allocate the next identifier for ``kind``, e.g. ``"company-000001"``."""
        if not kind:
            raise ValueError("Entity kind must be a non-empty string")
        number = self.counters.get(kind, 0) + 1
        self.counters[kind] = number
        return f"{kind}-{number:0{ID_NUMBER_WIDTH}d}"

    def issued(self, kind: str) -> int:
        """How many identifiers have been allocated for ``kind`` so far."""
        return self.counters.get(kind, 0)

    def state(self) -> dict[str, int]:
        """Serialisable counter state for inclusion in a save (V16.11)."""
        return dict(self.counters)

    @classmethod
    def from_state(cls, state: dict[str, int] | None) -> IdAllocator:
        """Restore an allocator from previously saved counter state."""
        return cls(counters=dict(state or {}))

    def reset(self) -> None:
        self.counters.clear()


def parse_id(identifier: str) -> tuple[str, int]:
    """Split an identifier into its kind and number.

    Raises ``ValueError`` if the identifier does not follow the allocator's
    format, so malformed references in a save surface during validation (V16.13)
    rather than silently resolving to nothing.
    """
    kind, separator, number = identifier.rpartition("-")
    if not separator or not kind or not number.isdigit():
        raise ValueError(f"Malformed entity identifier: {identifier!r}")
    return kind, int(number)


def new_save_id() -> str:
    """Create the unique Save ID required by V16.17.

    Unlike entity identifiers this is random rather than sequential: it must be
    globally unique across every save on a player's machine (and, later, across
    cloud saves), and it is generated exactly once when a save is created rather
    than during simulation, so it does not affect determinism.
    """
    return uuid.uuid4().hex
