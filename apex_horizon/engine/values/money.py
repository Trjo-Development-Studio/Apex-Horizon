"""Monetary values.

Design Bible V30.2 requires every monetary value in the game — personal cash,
company cash, investment amounts, fund capital — to be represented internally as
a single normalised currency unit, with the "$" symbol applied only when a value
is displayed. That single internal representation is what allows the future
multiple-currency expansion (V17.20) to become a presentation-layer feature
rather than a data model change.

V30.7 additionally requires full precision to be retained throughout every
computation, with rounding applied *only* at the moment a value is shown to the
player. Money therefore wraps ``Decimal`` rather than ``float``: binary floating
point cannot represent ordinary decimal amounts exactly, and those small errors
would compound across the hundreds of in-game years a save may span (V28.7).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard for type checkers only
    from .percentage import Percentage

# Values accepted when constructing Money or scaling it.
Numeric = int | str | Decimal | float

# Display rounding only ever happens here (V30.7).
CENTS = Decimal("0.01")


def to_decimal(value: Numeric | Money) -> Decimal:
    """Convert a supported value to ``Decimal`` without losing decimal precision.

    Floats are routed through ``str`` so that a literal such as ``0.1`` becomes
    exactly ``Decimal("0.1")`` rather than its binary approximation. Passing
    floats is supported for convenience but discouraged in simulation code.
    """
    if isinstance(value, Money):
        return value.amount
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        # bool subclasses int; accepting it would almost always be a mistake.
        raise TypeError("Money cannot be constructed from a bool")
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(f"Cannot interpret {type(value).__name__} as a monetary amount")


@dataclass(frozen=True, order=True)
class Money:
    """An immutable monetary amount in the game's single internal currency."""

    amount: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", to_decimal(self.amount))

    # -- construction ----------------------------------------------------
    @classmethod
    def zero(cls) -> Money:
        return cls(Decimal(0))

    # -- arithmetic ------------------------------------------------------
    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount - other.amount)

    def __mul__(self, factor: Numeric | Percentage) -> Money:
        """Scale by a plain number or a :class:`Percentage`.

        Multiplying money by money is meaningless and deliberately unsupported.
        """
        from .percentage import Percentage  # local import avoids a cycle

        if isinstance(factor, Money):
            raise TypeError("Cannot multiply Money by Money")
        if isinstance(factor, Percentage):
            return Money(self.amount * factor.fraction)
        return Money(self.amount * to_decimal(factor))

    __rmul__ = __mul__

    def __truediv__(self, divisor: Numeric | Money) -> Money | Decimal:
        """Dividing by a number yields Money; dividing by Money yields a ratio."""
        if isinstance(divisor, Money):
            return self.amount / divisor.amount
        return Money(self.amount / to_decimal(divisor))

    def __neg__(self) -> Money:
        return Money(-self.amount)

    def __abs__(self) -> Money:
        return Money(abs(self.amount))

    # -- inspection ------------------------------------------------------
    @property
    def is_zero(self) -> bool:
        return self.amount == 0

    @property
    def is_negative(self) -> bool:
        return self.amount < 0

    @property
    def is_positive(self) -> bool:
        return self.amount > 0

    def ratio_to(self, other: Money) -> Decimal:
        """This amount as a fraction of ``other``; zero when ``other`` is zero."""
        if other.amount == 0:
            return Decimal(0)
        return self.amount / other.amount

    # -- presentation ----------------------------------------------------
    def rounded(self, exponent: Decimal = CENTS) -> Decimal:
        """The amount rounded for display, leaving the stored value untouched."""
        return self.amount.quantize(exponent, rounding=ROUND_HALF_UP)

    def format(
        self,
        *,
        symbol: str = "$",
        decimals: int = 2,
        thousands: bool = True,
        signed: bool = False,
    ) -> str:
        """Render for display. This is the only place money is ever rounded.

        The "$" symbol lives here rather than in the stored value, per V30.2.
        """
        exponent = Decimal(1).scaleb(-decimals) if decimals > 0 else Decimal(1)
        value = self.rounded(exponent)
        grouping = "," if thousands else ""
        magnitude = format(abs(value), f"{grouping}.{decimals}f")
        if value < 0:
            return f"-{symbol}{magnitude}"
        return f"+{symbol}{magnitude}" if signed else f"{symbol}{magnitude}"

    def __str__(self) -> str:
        return self.format()

    def __repr__(self) -> str:
        return f"Money({str(self.amount)!r})"
