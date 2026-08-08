"""Apex Horizon entry point.

Run with::

    uv run python main.py

TODO (Milestone: terminal commands): Design Bible V15.18 specifies developer
commands executed from the launching terminal; argument parsing is added there.
"""

from __future__ import annotations

import sys


def main() -> int:
    from apex_horizon import __version__
    from apex_horizon.engine.config import ConfigError, get_config
    from apex_horizon.engine.logging_setup import configure_logging, get_logger

    log_path = configure_logging()
    logger = get_logger("apex_horizon.main")
    logger.info("Apex Horizon %s — logging to %s", __version__, log_path or "console only")

    # Configuration is required for the simulation to be meaningful, so a
    # failure here is reported clearly rather than retried (V15.13 covers
    # recoverable operations; a missing config file is not recoverable).
    try:
        get_config()
    except ConfigError as exc:
        logger.critical("Could not load gameplay configuration: %s", exc)
        print(f"Apex Horizon could not start: {exc}", file=sys.stderr)
        return 1

    try:
        from apex_horizon.ui import run_game
    except ModuleNotFoundError as exc:  # pragma: no cover - environment guard
        if exc.name == "pygame":
            print(
                "Pygame is not installed. Run: uv sync",
                file=sys.stderr,
            )
            return 1
        raise

    run_game()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
