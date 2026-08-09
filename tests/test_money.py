"""Tests for the Money type (Design Bible V30.2, V30.7)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from apex_horizon.engine.values import Money, Percentage


def test_construction_from_supported_types():
    assert Money(10).amount == Decimal(10)
    assert Money("10.25").amount == Decimal("10.25")
    assert Money(Decimal("3.5")).amount == Decimal("3.5")
    assert Money().amount == Decimal(0)
    assert Money.zero().is_zero


def test_float_input_avoids_binary_artifacts():
    # Routed through str, so 0.1 is exactly 0.1 rather than its binary form.
    assert Money(0.1).amount == Decimal("0.1")


def test_bool_is_rejected():
    with pytest.raises(TypeError):
        Money(True)


def test_unsupported_type_is_rejected():
    with pytest.raises(TypeError):
        Money([1])  # type: ignore[arg-type]  # deliberately wrong


def test_decimal_arithmetic_is_exact():
    # The defining reason Money wraps Decimal rather than float (V30.7):
    # 0.1 + 0.2 must equal exactly 0.3.
    assert Money("0.1") + Money("0.2") == Money("0.3")


def test_precision_is_retained_across_many_operations():
    total = Money.zero()
    for _ in range(1000):
        total = total + Money("0.01")
    assert total == Money("10.00")


def test_addition_and_subtraction():
    assert Money(10) + Money(5) == Money(15)
    assert Money(10) - Money(15) == Money(-5)


def test_adding_non_money_is_rejected():
    with pytest.raises(TypeError):
        Money(10) + 5  # type: ignore  # deliberately wrong


def test_multiplication_by_scalar_and_percentage():
    assert Money(100) * 3 == Money(300)
    assert 3 * Money(100) == Money(300)
    assert Money(200) * Percentage.from_percent(5) == Money(10)


def test_multiplying_money_by_money_is_rejected():
    with pytest.raises(TypeError):
        Money(10) * Money(2)  # type: ignore  # deliberately wrong


def test_division_by_scalar_and_by_money():
    assert Money(100) / 4 == Money(25)
    # Dividing money by money is a ratio, not money.
    assert Money(50) / Money(200) == Decimal("0.25")


def test_ratio_to_handles_zero_denominator():
    assert Money(10).ratio_to(Money.zero()) == Decimal(0)


def test_sign_helpers_and_negation():
    assert Money(-5).is_negative
    assert Money(5).is_positive
    assert (-Money(5)) == Money(-5)
    assert abs(Money(-5)) == Money(5)


def test_ordering_and_hashing():
    assert Money(5) < Money(10)
    assert sorted([Money(10), Money(1)]) == [Money(1), Money(10)]
    assert len({Money(5), Money(5)}) == 1


def test_formatting_applies_symbol_and_grouping():
    # The "$" lives at the presentation layer only (V30.2).
    assert Money(10_000).format() == "$10,000.00"
    assert Money(10_000).format(thousands=False) == "$10000.00"
    assert Money("1234.5").format(decimals=0) == "$1,235"
    assert Money(-250_000).format(decimals=0) == "-$250,000"
    assert Money(1500).format(signed=True, decimals=0) == "+$1,500"


def test_rounding_happens_only_at_display():
    money = Money("10.005")
    assert money.format() == "$10.01"
    # The stored value is untouched by display rounding.
    assert money.amount == Decimal("10.005")


def test_str_and_repr():
    assert str(Money(5)) == "$5.00"
    assert repr(Money(5)) == "Money('5')"
