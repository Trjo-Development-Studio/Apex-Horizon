"""Tests for the centralised configuration system (Design Bible V15.10)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.config import (
    Config,
    ConfigError,
    get_config,
    load_config,
    set_config,
)
from apex_horizon.engine.paths import config_dir


@pytest.fixture(autouse=True)
def _reset_shared_config():
    yield
    set_config(None)


def test_shipped_config_loads():
    config = load_config()
    assert config.source == config_dir() / "gameplay.toml"


def test_shipped_config_contains_design_bible_values():
    config = load_config()
    # V1.2 / V2.3 starting capital and V1.13 personal bankruptcy threshold.
    assert config.get_int("player.starting_personal_cash") == 10_000
    assert config.get_int("player.personal_bankruptcy_threshold") == -250_000
    # Project manager decisions recorded in config rather than hardcoded.
    assert config.get_int("company.founding_cost") == 25_000
    assert config.get_int("company.bankruptcy_cash_threshold") == -1_000_000
    # V13.4 / V13.5 simulation pacing.
    assert config.get_float("simulation.seconds_per_day") == 1.0
    assert config.get_list("simulation.speed_options") == [1, 2, 3]


def test_missing_key_without_default_raises():
    config = Config({"player": {"cash": 1}})
    with pytest.raises(ConfigError):
        config.get("player.missing")


def test_missing_key_returns_default():
    config = Config({"player": {"cash": 1}})
    assert config.get("player.missing", 42) == 42


def test_wrong_type_raises():
    config = Config({"player": {"cash": "lots"}})
    with pytest.raises(ConfigError):
        config.get_int("player.cash")


def test_bool_is_not_accepted_as_number():
    # bool subclasses int in Python; the config must not silently accept it.
    config = Config({"player": {"cash": True}})
    with pytest.raises(ConfigError):
        config.get_int("player.cash")


def test_int_is_promoted_to_float():
    config = Config({"simulation": {"seconds_per_day": 1}})
    assert config.get_float("simulation.seconds_per_day") == 1.0


def test_traversing_through_non_mapping_uses_default():
    config = Config({"player": {"cash": 1}})
    assert config.get("player.cash.nested", "fallback") == "fallback"


def test_missing_file_raises_config_error(tmp_path):
    with pytest.raises(ConfigError):
        load_config(tmp_path / "absent.toml")


def test_malformed_file_raises_config_error(tmp_path):
    bad = tmp_path / "bad.toml"
    bad.write_text("this is not = valid = toml", encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(bad)


def test_get_config_is_shared():
    set_config(Config({"a": {"b": 1}}))
    assert get_config().get_int("a.b") == 1
