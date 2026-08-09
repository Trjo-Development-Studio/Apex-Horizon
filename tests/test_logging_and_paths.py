"""Tests for logging setup (V15.12) and path resolution."""

from __future__ import annotations

import logging

import pytest

from apex_horizon.engine import paths
from apex_horizon.engine.logging_setup import (
    LOG_FILE_NAME,
    configure_logging,
    get_logger,
    reset_logging_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_logging():
    reset_logging_for_tests()
    yield
    reset_logging_for_tests()


def test_configure_logging_writes_to_file(tmp_path):
    log_path = configure_logging(directory=tmp_path)
    assert log_path == tmp_path / LOG_FILE_NAME

    get_logger("apex_horizon.test").error("example failure")
    logging.getLogger().handlers[-1].flush()
    assert log_path is not None
    assert "example failure" in log_path.read_text(encoding="utf-8")


def test_configure_logging_is_idempotent(tmp_path):
    first = configure_logging(directory=tmp_path)
    second = configure_logging(directory=tmp_path)
    assert first is not None
    # A second call must not add duplicate handlers or reconfigure logging.
    assert second is None


def test_configure_logging_survives_unwritable_directory(tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    # Must not raise: losing logs is never a reason to stop the player playing.
    assert configure_logging(directory=blocker / "logs") is None


def test_bundle_root_contains_config_directory():
    assert (paths.bundle_root() / "config").is_dir()
    assert paths.config_dir().name == "config"


def test_asset_path_is_under_assets_dir():
    path = paths.asset_path("sounds", "example.mp3")
    assert path.parent.parent == paths.assets_dir()


def test_user_data_paths_are_nested_consistently():
    assert paths.log_dir().parent == paths.user_data_dir()
    assert paths.save_dir().parent == paths.user_data_dir()


def test_not_frozen_when_running_from_source():
    assert paths.is_frozen() is False
