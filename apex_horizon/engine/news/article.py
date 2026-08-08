"""News articles.

Design Bible V10.3 sets the standard: news informs, it does not predict. An
article explains *why* something happened, giving texture and explanation to
the otherwise abstract movements of the Market and Economy (V10.18).

V10.9 requires every article to represent something that has actually happened,
and V10.24 that generation reads from the same simulation events that Analytics
and Employee Timelines draw on — so nothing is ever invented to fill space.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ..values import Percentage


class NewsTier(Enum):
    """The progression of V10.4, unlocked through the News branch (V6.6.2)."""

    BASIC = 1      # individual company updates (V10.5)
    MARKET = 2     # industry trends and market sentiment (V10.6)
    ECONOMIC = 3   # growth, recession, inflation, banking (V10.7)
    BREAKING = 4   # major unexpected events (V10.8)

    def __str__(self) -> str:
        return {
            NewsTier.BASIC: "Company",
            NewsTier.MARKET: "Market",
            NewsTier.ECONOMIC: "Economy",
            NewsTier.BREAKING: "Breaking",
        }[self]


@dataclass
class NewsArticle:
    """One story, traceable to a real simulation event."""

    id: str
    day: int
    tier: NewsTier
    headline: str
    body: str
    agency: str = ""
    #: The company the story concerns, when it concerns one.
    company_id: str | None = None
    #: How strongly this story should move that company's price (V10.10).
    impact: Percentage | None = None

    @property
    def is_breaking(self) -> bool:
        return self.tier is NewsTier.BREAKING

    def state(self) -> dict:
        return {
            "id": self.id,
            "day": self.day,
            "tier": self.tier.name,
            "headline": self.headline,
            "body": self.body,
            "agency": self.agency,
            "company_id": self.company_id,
            "impact": str(self.impact.fraction) if self.impact else None,
        }

    @classmethod
    def from_state(cls, data: dict) -> NewsArticle:
        impact = data.get("impact")
        return cls(
            id=data["id"],
            day=int(data["day"]),
            tier=NewsTier[data.get("tier", "BASIC")],
            headline=data["headline"],
            body=data.get("body", ""),
            agency=data.get("agency", ""),
            company_id=data.get("company_id"),
            impact=Percentage(impact) if impact else None,
        )
