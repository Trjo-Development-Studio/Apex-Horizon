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

__all__ = [
    "Config",
    "ConfigError",
    "OperationResult",
    "configure_logging",
    "get_config",
    "get_logger",
    "load_config",
    "log_simulation_event",
    "notify_player",
    "run_with_retry",
    "set_config",
    "subscribe_error_notifier",
]
