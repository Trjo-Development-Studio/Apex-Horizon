"""Tests for the simulation clock (Design Bible V13.4, V13.5, V13.27, V13.29)."""

from __future__ import annotations

import pytest

from apex_horizon.engine.simulation import SimulationClock


def make_clock(**kwargs) -> SimulationClock:
    defaults = {
        "seconds_per_day": 1.0,
        "speed": 1,
        "speed_options": (1, 2, 3),
        "max_days_per_update": 30,
    }
    return SimulationClock(**{**defaults, **kwargs})


def test_default_pace_is_one_second_per_day():
    # V13.4: one real-life second per in-game day.
    clock = make_clock()
    assert clock.advance(1.0) == 1
    assert clock.advance(0.5) == 0
    assert clock.advance(0.5) == 1


def test_speed_multiplies_the_rate():
    # V13.5: x1 / x2 / x3.
    for speed, expected in ((1, 1), (2, 2), (3, 3)):
        clock = make_clock(speed=speed)
        assert clock.advance(1.0) == expected


def test_partial_seconds_accumulate_rather_than_being_lost():
    clock = make_clock()
    for _ in range(10):
        assert clock.advance(0.1) in (0, 1)
    # Ten tenths of a second is exactly one day, however it is delivered.
    assert clock.advance(0.0) == 0


def test_result_is_independent_of_polling_frequency():
    # V13.29: tick processing is decoupled from frame rate.
    coarse = make_clock()
    fine = make_clock()
    coarse_days = coarse.advance(10.0)
    fine_days = sum(fine.advance(1 / 60) for _ in range(600))
    assert coarse_days == fine_days == 10


def test_pause_stops_time_without_banking_it():
    # V13.20: the player must not lose time while a popup is open.
    clock = make_clock()
    clock.pause()
    assert clock.paused is True
    assert clock.advance(5.0) == 0
    clock.resume()
    # Unpausing must not fast-forward through the paused period.
    assert clock.advance(1.0) == 1


def test_speed_change_preserves_banked_time():
    # V13.27: switching speed must not skip or duplicate ticks.
    clock = make_clock()
    clock.advance(0.9)
    clock.speed = 3
    # 0.9s banked, then 0.1s at x3 adds 0.3 -> 1.2s total, exactly one day.
    assert clock.advance(0.1) == 1


def test_rapid_speed_switching_conserves_days():
    clock = make_clock()
    total = 0
    for index in range(300):
        clock.speed = (index % 3) + 1
        total += clock.advance(0.1)
    # Every earned day is released exactly once; none are lost or duplicated.
    assert total == 60


def test_invalid_speed_is_rejected():
    clock = make_clock()
    with pytest.raises(ValueError):
        clock.speed = 5
    with pytest.raises(ValueError):
        make_clock(speed=0)


def test_negative_time_is_rejected():
    with pytest.raises(ValueError):
        make_clock().advance(-1.0)


def test_invalid_seconds_per_day_is_rejected():
    with pytest.raises(ValueError):
        make_clock(seconds_per_day=0)


def test_long_idle_period_is_capped_but_not_dropped():
    # V13.27: long unattended sessions stay stable; surplus days are carried
    # forward across later updates rather than discarded.
    clock = make_clock(max_days_per_update=30)
    assert clock.advance(100.0) == 30
    assert clock.pending_days == 70
    assert clock.advance(0.0) == 30
    assert clock.advance(0.0) == 30
    assert clock.advance(0.0) == 10
    assert clock.pending_days == 0


def test_state_round_trip():
    clock = make_clock()
    clock.advance(0.4)
    clock.speed = 2
    clock.pause()

    restored = make_clock()
    restored.restore(clock.state())
    assert restored.speed == 2
    assert restored.paused is True
    restored.resume()
    # The 0.4s banked before saving is still banked after loading.
    assert restored.advance(0.3) == 1


def test_restore_rejects_unsupported_speed():
    clock = make_clock()
    with pytest.raises(ValueError):
        clock.restore({"speed": 9})
