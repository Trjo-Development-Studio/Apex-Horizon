"""Engine layer — configuration, logging, error handling, and (later) the
simulation itself.

Design Bible V15.3 specifies a layer-based architecture: gameplay systems live
inside the engine with a clean internal structure rather than each receiving its
own top-level folder.
"""

from .config import Config, ConfigError, get_config, load_config, set_config
from .errors import (
    OperationResult,
    log_simulation_event,
    notify_player,
    run_with_retry,
    subscribe_error_notifier,
)
from .logging_setup import configure_logging, get_logger
from .values import (
    Calendar,
    EntityKind,
    IdAllocator,
    Money,
    Percentage,
    SimulationDate,
    get_calendar,
    new_save_id,
    now_iso,
)

__all__ = [
    "Calendar",
    "Config",
    "ConfigError",
    "EntityKind",
    "IdAllocator",
    "Money",
    "OperationResult",
    "Percentage",
    "SimulationDate",
    "configure_logging",
    "get_calendar",
    "get_config",
    "get_logger",
    "load_config",
    "log_simulation_event",
    "new_save_id",
    "notify_player",
    "now_iso",
    "run_with_retry",
    "set_config",
    "subscribe_error_notifier",
]
