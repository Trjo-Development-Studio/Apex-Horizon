"""Time and simulation — Design Bible Volumes 13 and 29.

The simulation engine owns in-game time and executes the ten daily phases in the
order Volume 29 defines. Gameplay systems register handlers for the phases they
belong to rather than calling one another directly, keeping each system modular
(V15.7) while the engine guarantees a single, deterministic processing order.
"""

from .clock import SimulationClock
from .engine import SimulationEngine
from .phases import (
    PHASE_ORDER,
    BoundaryHandler,
    PeriodBoundary,
    PhaseHandler,
    SimulationContext,
    SimulationPhase,
)

__all__ = [
    "PHASE_ORDER",
    "BoundaryHandler",
    "PeriodBoundary",
    "PhaseHandler",
    "SimulationClock",
    "SimulationContext",
    "SimulationEngine",
    "SimulationPhase",
]
