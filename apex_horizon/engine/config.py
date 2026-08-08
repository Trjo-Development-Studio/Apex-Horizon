"""Centralised gameplay configuration.

Design Bible V15.10 requires configuration to live in dedicated files rather
than being scattered through source code, so that balance changes never require
editing simulation logic. Every system reads its tunable values through this
module instead of defining literals of its own.

Values are addressed with dotted paths matching the TOML structure::

    config = get_config()
    starting_cash = config.get_int("player.starting_personal_cash")
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from .paths import config_dir

# Name of the primary gameplay configuration file inside ``config/``.
GAMEPLAY_CONFIG_FILE = "gameplay.toml"

# Sentinel distinguishing "no default supplied" from an explicit ``None``.
_MISSING = object()


class ConfigError(Exception):
    """Raised when configuration is missing, malformed, or of the wrong type."""


class Config:
    """Read-only access to configuration values loaded from a TOML file."""

    def __init__(self, data: dict[str, Any], source: Path | None = None):
        self._data = data
        self.source = source

    def get(self, path: str, default: Any = _MISSING) -> Any:
        """Return the value at a dotted ``path``, or ``default`` if absent.

        Raises ``ConfigError`` when the key is absent and no default is given,
        so that a missing configuration value fails loudly during development
        rather than silently defaulting to zero somewhere in the simulation.
        """
        node: Any = self._data
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                if default is _MISSING:
                    raise ConfigError(f"Missing configuration value: {path!r}")
                return default
            node = node[part]
        return node

    def _typed(self, path: str, expected: type, default: Any) -> Any:
        value = self.get(path, default)
        # bool is a subclass of int; reject it explicitly for numeric lookups so
        # a stray "true" in config can never masquerade as a number.
        if expected in (int, float) and isinstance(value, bool):
            raise ConfigError(f"Configuration value {path!r} must be {expected.__name__}")
        if expected is float and isinstance(value, int):
            return float(value)
        if not isinstance(value, expected):
            raise ConfigError(
                f"Configuration value {path!r} must be {expected.__name__}, "
                f"got {type(value).__name__}"
            )
        return value

    def get_int(self, path: str, default: Any = _MISSING) -> int:
        return self._typed(path, int, default)

    def get_float(self, path: str, default: Any = _MISSING) -> float:
        return self._typed(path, float, default)

    def get_str(self, path: str, default: Any = _MISSING) -> str:
        return self._typed(path, str, default)

    def get_bool(self, path: str, default: Any = _MISSING) -> bool:
        return self._typed(path, bool, default)

    def get_list(self, path: str, default: Any = _MISSING) -> list[Any]:
        return self._typed(path, list, default)

    def as_dict(self) -> dict[str, Any]:
        """A copy of the raw configuration data, primarily for debugging."""
        return dict(self._data)


def load_config(path: Path | None = None) -> Config:
    """Load configuration from ``path`` (defaults to ``config/gameplay.toml``)."""
    config_path = path or (config_dir() / GAMEPLAY_CONFIG_FILE)
    try:
        with open(config_path, "rb") as handle:
            data = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Malformed configuration file {config_path}: {exc}") from exc
    return Config(data, source=config_path)


_config: Config | None = None


def get_config() -> Config:
    """Return the shared configuration, loading it on first use."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def set_config(config: Config | None) -> None:
    """Replace the shared configuration (used by tests and debug tooling)."""
    global _config
    _config = config
