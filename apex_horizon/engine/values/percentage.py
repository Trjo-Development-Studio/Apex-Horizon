"""Percentage values.

Design Bible V30.3 requires percentage-based values — interest rates (V17.13),
inflation (V7.5), skill-derived probabilities (V5.4) — to be stored internally
as normalised fractional values, with the "%" symbol applied only at the
presentation layer (V15.5).

Storing ``0.05`` rather than ``5`` removes an entire class of bug: a percentage
from the Economy System and one from the Employee System can never be
misinterpreted or scaled differently from one another (V30.10).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .money import Numeric, to_decimal

ONE_HUNDRED = Decimal(100)


@dataclass(frozen=True, order=True)
class Percentage:
    """An immutable percentage stored as a fraction (5% is stored as 0.05)."""

    fraction: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "fraction", to_decimal(self.fraction))

    # -- construction ----------------------------------------------------
    @classmethod
    def zero(cls) -> Percentage:
        return cls(Decimal(0))

    @classmethod
    def from_percent(cls, percent: Numeric) -> Percentage:
        """Build from a human-facing percentage: ``from_percent(5)`` is 5%."""
        return cls(to_decimal(percent) / ONE_HUNDRED)

    @classmethod
    def from_ratio(cls, part: Numeric, whole: Numeric) -> Percentage:
        """Build from a part and a whole; a zero whole yields 0%."""
        whole_value = to_decimal(whole)
        if whole_value == 0:
            return cls(Decimal(0))
        return cls(to_decimal(part) / whole_value)

    # -- inspection ------------------------------------------------------
    @property
    def as_percent(self) -> Decimal:
        """The value expressed in percentage points (0.05 -> 5)."""
        return self.fraction * ONE_HUNDRED

    @property
    def is_zero(self) -> bool:
        return self.fraction == 0

    @property
    def is_negative(self) -> bool:
        return self.fraction < 0

    # -- arithmetic ------------------------------------------------------
    def __add__(self, other: Percentage) -> Percentage:
        if not isinstance(other, Percentage):
            return NotImplemented
        return Percentage(self.fraction + other.fraction)

    def __sub__(self, other: Percentage) -> Percentage:
        if not isinstance(other, Percentage):
            return NotImplemented
        return Percentage(self.fraction - other.fraction)

    def __mul__(self, factor: Numeric) -> Percentage:
        if isinstance(factor, Percentage):
            return Percentage(self.fraction * factor.fraction)
        return Percentage(self.fraction * to_decimal(factor))

    __rmul__ = __mul__

    def __neg__(self) -> Percentage:
        return Percentage(-self.fraction)

    def applied_to(self, value: Decimal | int | Percentage) -> Decimal:
        """This percentage of a numeric value (for Money, use ``money * pct``)."""
        if isinstance(value, Percentage):
            return self.fraction * value.fraction
        return self.fraction * to_decimal(value)

    def scale_factor(self) -> Decimal:
        """``1 + fraction`` — the multiplier for applying a percentage change."""
        return Decimal(1) + self.fraction

    # -- presentation ----------------------------------------------------
    def format(self, *, decimals: int = 2, signed: bool = False) -> str:
        """Render for display. Rounding happens only here (V30.7)."""
        exponent = Decimal(1).scaleb(-decimals) if decimals > 0 else Decimal(1)
        value = self.as_percent.quantize(exponent, rounding=ROUND_HALF_UP)
        text = f"{value:.{decimals}f}%"
        return f"+{text}" if signed and value > 0 else text

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return f"Percentage({str(self.fraction)!r})"
