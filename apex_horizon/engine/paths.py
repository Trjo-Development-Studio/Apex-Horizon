"""Filesystem locations used across the game.

Centralising path resolution keeps the rest of the codebase free of assumptions
about where the project lives, and lets a frozen (PyInstaller) build resolve
bundled data from its extraction directory while still writing player data to a
normal, persistent user directory.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Directory name used for player-writable data (saves, logs) outside the project.
APP_DIR_NAME = "apex-horizon"


def is_frozen() -> bool:
    """True when running from a PyInstaller build rather than from source."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path:
    """Root directory containing read-only bundled data (config, assets).

    From source this is the repository root. In a frozen build PyInstaller
    extracts bundled data to a temporary directory exposed as ``sys._MEIPASS``.
    """
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    # paths.py -> engine -> apex_horizon -> repository root
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    """Directory holding the gameplay configuration files (V15.10)."""
    return bundle_root() / "config"


def assets_dir() -> Path:
    """Directory holding bundled game assets."""
    return bundle_root() / "assets"


def asset_path(*parts: str) -> Path:
    """Path to a file inside ``assets/`` (e.g. ``asset_path("sounds", "x.mp3")``)."""
    return assets_dir().joinpath(*parts)


def user_data_dir() -> Path:
    """Writable directory for player data such as saves and logs.

    Running from source keeps this inside the project so development artefacts
    stay together; a frozen build uses the platform's standard user data
    location so the game never depends on being installed somewhere writable.
    """
    if not is_frozen():
        return bundle_root()
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME


def log_dir() -> Path:
    """Directory for log files (V15.12)."""
    return user_data_dir() / "logs"


def save_dir() -> Path:
    """Directory for save files (V16)."""
    return user_data_dir() / "saves"
