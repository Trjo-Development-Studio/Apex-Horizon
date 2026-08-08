"""Tests for the Percentage type (Design Bible V30.3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apex_horizon.engine.values import Money, Percentage


def test_stored_as_fraction_not_percentage_points():
    # V30.3: 5% is stored as 0.05, never as 5.
    assert Percentage.from_percent(5).fraction == Decimal("0.05")
    assert Percentage(Decimal("0.05")).as_percent == Decimal(5)


def test_zero_and_defaults():
    assert Percentage().is_zero
    assert Percentage.zero().is_zero


def test_from_ratio():
    assert Percentage.from_ratio(25, 100) == Percentage(Decimal("0.25"))
    # A zero whole must not raise; it yields 0%.
    assert Percentage.from_ratio(5, 0).is_zero


def test_arithmetic():
    assert Percentage.from_percent(5) + Percentage.from_percent(3) == Percentage.from_percent(8)
    assert Percentage.from_percent(5) - Percentage.from_percent(8) == Percentage.from_percent(-3)
    assert Percentage.from_percent(5) * 2 == Percentage.from_percent(10)
    assert (-Percentage.from_percent(5)).is_negative


def test_adding_non_percentage_is_rejected():
    with pytest.raises(TypeError):
        Percentage.from_percent(5) + 1


def test_applied_to_and_scale_factor():
    assert Percentage.from_percent(10).applied_to(200) == Decimal(20)
    assert Percentage.from_percent(10).scale_factor() == Decimal("1.1")


def test_interacts_with_money():
    salary = Money(50_000)
    assert salary * Percentage.from_percent(2) == Money(1000)


def test_formatting_applies_symbol_at_display_only():
    assert Percentage.from_percent(5).format() == "5.00%"
    assert Percentage.from_percent("2.5").format(decimals=1) == "2.5%"
    assert Percentage.from_percent(5).format(signed=True, decimals=0) == "+5%"
    assert Percentage.from_percent(-5).format(decimals=0) == "-5%"


def test_ordering_and_hashing():
    assert Percentage.from_percent(1) < Percentage.from_percent(2)
    assert len({Percentage.from_percent(1), Percentage.from_percent(1)}) == 1


def test_str_and_repr():
    assert str(Percentage.from_percent(5)) == "5.00%"
    assert "Percentage(" in repr(Percentage.from_percent(5))
