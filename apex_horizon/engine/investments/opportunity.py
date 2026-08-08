"""Opportunities and positions.

Design Bible V8.24 asks for each stage of the investment workflow to be a
distinct, independently-timed process rather than one atomic transaction, so
that a partly-completed workflow — an opportunity approved but not yet executed
— is a valid, inspectable state rather than a transient implementation detail.

These are the records that make that possible: an :class:`Opportunity` moves
through discovery, review and execution, and becomes a :class:`Position` the
company holds until an investor decides to sell.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..values import Money, Percentage


class Stage(Enum):
    """Where an opportunity has reached in the workflow of V8.3."""

    DISCOVERED = "Awaiting review"
    APPROVED = "Approved, awaiting execution"
    REJECTED = "Rejected"
    EXECUTED = "Invested"
    EXPIRED = "Expired"

    def __str__(self) -> str:
        return self.value


@dataclass
class Opportunity:
    """Something a Research employee thinks is worth investing in (V8.4)."""

    id: str
    company_id: str
    discovered_by: str
    discovered_on_day: int
    #: How reliable the research is, from the researcher's skill (V8.4, V9.5).
    confidence: float
    #: The return the researcher believes is available. Research reduces
    #: uncertainty but never removes it (V9.3), so this is an estimate that the
    #: market is under no obligation to honour.
    expected_return: Percentage
    stage: Stage = Stage.DISCOVERED
    reviewed_by: str | None = None
    decided_on_day: int | None = None
    rejection_reason: str = ""

    @property
    def is_open(self) -> bool:
        return self.stage in (Stage.DISCOVERED, Stage.APPROVED)

    def state(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "discovered_by": self.discovered_by,
            "discovered_on_day": self.discovered_on_day,
            "confidence": self.confidence,
            "expected_return": str(self.expected_return.fraction),
            "stage": self.stage.name,
            "reviewed_by": self.reviewed_by,
            "decided_on_day": self.decided_on_day,
            "rejection_reason": self.rejection_reason,
        }

    @classmethod
    def from_state(cls, data: dict) -> Opportunity:
        return cls(
            id=data["id"],
            company_id=data["company_id"],
            discovered_by=data["discovered_by"],
            discovered_on_day=int(data["discovered_on_day"]),
            confidence=float(data["confidence"]),
            expected_return=Percentage(data["expected_return"]),
            stage=Stage[data.get("stage", "DISCOVERED")],
            reviewed_by=data.get("reviewed_by"),
            decided_on_day=data.get("decided_on_day"),
            rejection_reason=data.get("rejection_reason", ""),
        )


@dataclass
class Position:
    """Shares the company holds (V8.9).

    There is no fixed holding period: a position lasts days, weeks, months or
    years depending on market conditions and the investor's own judgement.
    """

    id: str
    company_id: str
    shares: int
    average_price: Money
    opened_on_day: int
    opened_by: str
    #: The gain and loss thresholds this investor set, from their risk
    #: tolerance (V8.10, V8.13).
    target_return: Percentage
    stop_loss: Percentage
    closed_on_day: int | None = None
    proceeds: Money = field(default_factory=Money.zero)
    realised_gain: Money = field(default_factory=Money.zero)
    close_reason: str = ""

    @property
    def is_open(self) -> bool:
        return self.closed_on_day is None

    @property
    def cost_basis(self) -> Money:
        return self.average_price * self.shares

    def value_at(self, price: Money) -> Money:
        return price * self.shares

    def unrealised_return(self, price: Money) -> Percentage:
        if self.average_price.is_zero:
            return Percentage.zero()
        return Percentage(
            (price.amount - self.average_price.amount) / self.average_price.amount
        )

    def holding_days(self, day: int) -> int:
        return (self.closed_on_day or day) - self.opened_on_day

    def state(self) -> dict:
        return {
            "id": self.id,
            "company_id": self.company_id,
            "shares": self.shares,
            "average_price": str(self.average_price.amount),
            "opened_on_day": self.opened_on_day,
            "opened_by": self.opened_by,
            "target_return": str(self.target_return.fraction),
            "stop_loss": str(self.stop_loss.fraction),
            "closed_on_day": self.closed_on_day,
            "proceeds": str(self.proceeds.amount),
            "realised_gain": str(self.realised_gain.amount),
            "close_reason": self.close_reason,
        }

    @classmethod
    def from_state(cls, data: dict) -> Position:
        return cls(
            id=data["id"],
            company_id=data["company_id"],
            shares=int(data["shares"]),
            average_price=Money(data["average_price"]),
            opened_on_day=int(data["opened_on_day"]),
            opened_by=data["opened_by"],
            target_return=Percentage(data["target_return"]),
            stop_loss=Percentage(data["stop_loss"]),
            closed_on_day=data.get("closed_on_day"),
            proceeds=Money(data.get("proceeds", "0")),
            realised_gain=Money(data.get("realised_gain", "0")),
            close_reason=data.get("close_reason", ""),
        )
