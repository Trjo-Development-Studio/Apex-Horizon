"""Shared value types implementing the Data Standards of Design Bible V30.

V30.9 requires these standards to be enforced through shared internal types used
by every gameplay system, rather than through developer convention alone. Every
system therefore expresses money as :class:`Money`, percentages as
:class:`Percentage`, and in-game time as :class:`SimulationDate`, so a value can
never be misinterpreted or rounded differently as it crosses between systems.
"""

from .identifiers import EntityKind, IdAllocator, new_save_id, parse_id
from .money import Money, to_decimal
from .percentage import Percentage
from .simulation_date import (
    WEEKDAY_NAMES,
    Calendar,
    SimulationDate,
    format_calendar_label,
    get_calendar,
    set_calendar,
)
from .timestamps import now_iso, parse_iso, to_iso, utc_now

__all__ = [
    "WEEKDAY_NAMES",
    "Calendar",
    "EntityKind",
    "IdAllocator",
    "Money",
    "Percentage",
    "SimulationDate",
    "format_calendar_label",
    "get_calendar",
    "new_save_id",
    "now_iso",
    "parse_id",
    "parse_iso",
    "set_calendar",
    "to_decimal",
    "to_iso",
    "utc_now",
]
