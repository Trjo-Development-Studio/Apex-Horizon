"""Tests for the retry and error-reporting policy (Design Bible V15.13)."""

from __future__ import annotations

import pytest

from apex_horizon.engine import errors
from apex_horizon.engine.config import Config, set_config


@pytest.fixture(autouse=True)
def _clean_notifiers():
    errors.clear_error_notifiers()
    yield
    errors.clear_error_notifiers()
    set_config(None)


def test_successful_operation_runs_once():
    calls = []

    def operation():
        calls.append(1)
        return "done"

    result = errors.run_with_retry(operation, description="Test operation")
    assert result.succeeded is True
    assert result.value == "done"
    assert result.attempts == 1
    assert len(calls) == 1


def test_operation_succeeding_on_final_attempt():
    # V15.13: the initial attempt plus two automatic retries.
    attempts = {"count": 0}

    def operation():
        attempts["count"] += 1
        if attempts["count"] < errors.DEFAULT_ATTEMPTS:
            raise RuntimeError("transient")
        return "recovered"

    result = errors.run_with_retry(operation, description="Flaky operation")
    assert result.succeeded is True
    assert result.value == "recovered"
    assert attempts["count"] == errors.DEFAULT_ATTEMPTS


def test_failing_operation_retries_then_notifies():
    attempts = {"count": 0}
    seen: list[str] = []

    def operation():
        attempts["count"] += 1
        raise RuntimeError("always fails")

    errors.subscribe_error_notifier(seen.append)
    result = errors.run_with_retry(operation, description="Doomed operation")

    assert result.succeeded is False
    assert isinstance(result.error, RuntimeError)
    # Exactly three attempts: the original plus two retries.
    assert attempts["count"] == errors.DEFAULT_ATTEMPTS
    assert len(seen) == 1
    assert "Doomed operation" in seen[0]


def test_failure_message_includes_discord_url_when_configured():
    set_config(Config({"support": {"discord_invite_url": "https://example.invalid/x"}}))
    message = errors.build_failure_message("Saving")
    assert "https://example.invalid/x" in message


def test_failure_message_without_discord_url():
    set_config(Config({"support": {"discord_invite_url": ""}}))
    message = errors.build_failure_message("Saving")
    assert "report this issue" in message.lower()


def test_broken_notifier_does_not_escalate():
    def bad_notifier(_message):
        raise ValueError("notifier exploded")

    errors.subscribe_error_notifier(bad_notifier)
    # Must not raise: a broken notifier cannot become a second failure.
    errors.notify_player("hello")


def test_unsubscribe_stops_notifications():
    seen: list[str] = []
    errors.subscribe_error_notifier(seen.append)
    errors.unsubscribe_error_notifier(seen.append)
    errors.notify_player("ignored")
    assert seen == []


def test_unexpected_exception_type_propagates():
    def operation():
        raise KeyboardInterrupt

    # Only the expected exception types are retried; anything else propagates
    # so genuinely fatal conditions are never silently swallowed.
    with pytest.raises(KeyboardInterrupt):
        errors.run_with_retry(operation, description="Interrupted")
