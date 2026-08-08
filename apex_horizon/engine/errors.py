"""Safe failure handling for operations that can reasonably fail.

Design Bible V15.13 defines the policy precisely: attempt the operation, retry
automatically, retry a second time, and only if it still fails log the complete
error, notify the player, and ask them to report the issue. Gameplay should
continue wherever possible — a non-critical failure must never terminate the
game (see also V19 and the "fail safely" requirement in the project brief).

Errors are surfaced to the player through subscriber callbacks rather than by
importing any interface code here, keeping game logic independent of the UI as
required by V15.5.
"""

from __future__ import annotations

import traceback
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from .config import get_config
from .logging_setup import get_logger

T = TypeVar("T")

logger = get_logger(__name__)

# V15.13: the initial attempt plus two automatic retries.
DEFAULT_ATTEMPTS = 3

# Callbacks invoked with a player-facing message when an operation finally fails.
_notifiers: list[Callable[[str], None]] = []


@dataclass
class OperationResult(Generic[T]):
    """Outcome of an operation run under the retry policy."""

    succeeded: bool
    value: T | None = None
    error: BaseException | None = None
    attempts: int = 0


def subscribe_error_notifier(callback: Callable[[str], None]) -> None:
    """Register a callback that presents error messages to the player."""
    if callback not in _notifiers:
        _notifiers.append(callback)


def unsubscribe_error_notifier(callback: Callable[[str], None]) -> None:
    """Remove a previously registered error notifier."""
    if callback in _notifiers:
        _notifiers.remove(callback)


def clear_error_notifiers() -> None:
    """Remove every registered notifier (used by tests)."""
    _notifiers.clear()


def _report_url() -> str:
    """Where players are asked to report unrecoverable errors (V15.13)."""
    try:
        return get_config().get_str("support.discord_invite_url", "")
    except Exception:  # configuration itself may be what failed
        return ""


def build_failure_message(description: str) -> str:
    """Compose the player-facing message shown when an operation fails."""
    message = f"{description} failed after {DEFAULT_ATTEMPTS} attempts."
    url = _report_url()
    # TODO: the project manager will supply the official Discord invite; until
    # then the message asks for a report without naming a destination.
    if url:
        return f"{message} Please report this issue in the official Discord server: {url}"
    return f"{message} Please report this issue to the developers."


def notify_player(message: str) -> None:
    """Send a message to every registered notifier, ignoring notifier failures."""
    # Iterate over a copy so a notifier may unsubscribe itself while running.
    for callback in _notifiers.copy():
        try:
            callback(message)
        except Exception:
            # A broken notifier must never escalate into a second failure.
            logger.exception("Error notifier raised an exception.")


def run_with_retry(
    operation: Callable[[], T],
    *,
    description: str,
    attempts: int = DEFAULT_ATTEMPTS,
    expected: tuple[type[BaseException], ...] = (Exception,),
) -> OperationResult[T]:
    """Run ``operation`` under the Design Bible's retry policy (V15.13).

    Returns an ``OperationResult`` rather than raising, so callers can decide
    how to continue. Warnings are logged for each failed attempt; the final
    failure is logged in full with its traceback and reported to the player.
    """
    last_error: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            value = operation()
        except expected as exc:
            last_error = exc
            if attempt < attempts:
                logger.warning(
                    "%s failed (attempt %d of %d): %s. Retrying.",
                    description, attempt, attempts, exc,
                )
                continue
            logger.error(
                "%s failed after %d attempts: %s\n%s",
                description,
                attempts,
                exc,
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            )
            notify_player(build_failure_message(description))
            return OperationResult(succeeded=False, error=last_error, attempts=attempt)
        else:
            if attempt > 1:
                logger.info("%s succeeded on attempt %d.", description, attempt)
            return OperationResult(succeeded=True, value=value, attempts=attempt)

    # Unreachable while attempts >= 1; kept so the contract holds for attempts <= 0.
    return OperationResult(succeeded=False, error=last_error, attempts=0)


def log_simulation_event(message: str, *args: Any) -> None:
    """Record an important simulation event (V15.12).

    The News System and Employee Timelines are expected to read from the same
    event history in later milestones (V10.24), so simulation events are logged
    through one deliberate entry point rather than ad-hoc logger calls.
    """
    logger.info(message, *args)
