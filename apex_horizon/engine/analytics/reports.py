"""Analytics reports.

V9 asks for analytics across five areas — the company, its employees, the
market, investments, and how all of them have changed over time — and V9.22 is
explicit that analysis must be separated from the simulation. Nothing here
computes anything the simulation depends on. Every report reads state that
already exists and arranges it for reading, so a report can be added, changed or
removed without any risk to the game.

Depth is gated by tier (V9.4): the Basic tier answers "what is happening", and
each level above it adds the kind of question a player only starts asking once
they have a reason to. A locked report is absent rather than empty — V9.21
would rather show nothing than a figure the player cannot act on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..logging_setup import get_logger
from ..values import Percentage

logger = get_logger(__name__)


class AnalyticsTier(Enum):
    """How deep the player's analytics go (V9.4, raised via the Unlock Tree)."""

    BASIC = 1
    DETAILED = 2
    ADVANCED = 3
    COMPLETE = 4

    def __str__(self) -> str:
        return {"BASIC": "Basic", "DETAILED": "Detailed",
                "ADVANCED": "Advanced", "COMPLETE": "Complete"}[self.name]


@dataclass(frozen=True)
class Metric:
    """One figure in a report, with the words needed to read it."""

    label: str
    value: str
    note: str = ""
    #: True for good, False for bad, None when a value is merely neutral.
    positive: bool | None = None


@dataclass
class Report:
    """A named group of metrics, ready to be drawn (V9.22)."""

    title: str
    metrics: list[Metric] = field(default_factory=list)
    note: str = ""

    def add(self, label: str, value, note: str = "",
            positive: bool | None = None) -> None:
        self.metrics.append(Metric(label, str(value), note, positive))


class AnalyticsService:
    """Assembles the game's reports from state that already exists."""

    def __init__(self, context, *, history=None):
        self.context = context
        self.history = history
        self.tier: AnalyticsTier = AnalyticsTier.BASIC
        #: False until Basic Analytics is unlocked (V6.6.1).
        self.enabled: bool = True
        #: The deepest internal business intelligence (V9.9), its own unlock.
        self.company_analytics: bool = False

    def _has(self, tier: AnalyticsTier) -> bool:
        return self.tier.value >= tier.value

    def reports(self) -> list[Report]:
        """Every report the player has unlocked, in reading order."""
        if not self.enabled:
            return []
        built = [
            self.company_report(),
            self.employee_report(),
            self.market_report(),
            self.investment_report(),
            self.company_intelligence_report(),
            self.historical_report(),
        ]
        return [report for report in built if report is not None]

    # -- the company (V9.5) ------------------------------------------------
    def company_report(self) -> Report | None:
        company = getattr(self.context, "company", None)
        if company is None:
            return None
        finances = company.finances
        report = Report("Company", note="How the business itself is doing")
        report.add("Cash", finances.cash.format(decimals=0),
                   "Available to spend", positive=not finances.cash.is_negative)
        profit = finances.profit_this_week
        report.add("Profit this week", profit.format(decimals=0, signed=True),
                   "Revenue less expenses", positive=not profit.is_negative)

        if self._has(AnalyticsTier.DETAILED):
            margin = finances.profit_margin()
            report.add("Profit margin", margin.format(),
                       "Profit as a share of revenue",
                       positive=not margin.is_negative)
            report.add("Net worth", finances.net_worth().format(decimals=0),
                       "Assets less liabilities")
        if self._has(AnalyticsTier.ADVANCED):
            lifetime = finances.lifetime_profit
            report.add("Lifetime profit", lifetime.format(decimals=0, signed=True),
                       "Since the company was founded",
                       positive=not lifetime.is_negative)
        return report

    # -- the people (V9.6) -------------------------------------------------
    def employee_report(self) -> Report | None:
        company = getattr(self.context, "company", None)
        roster = getattr(company, "employees", None) if company else None
        if roster is None:
            return None
        report = Report("Employees", note="Who you have, and what they produce")
        report.add("Headcount", f"{len(roster)} of {roster.capacity}",
                   "Against your current capacity")
        report.add("Monthly salaries", roster.monthly_salary_bill().format(decimals=0),
                   "What the payroll costs")

        if self._has(AnalyticsTier.DETAILED):
            report.add("Research output", f"{roster.research_output:.2f}",
                       "Drives what opportunities are found")
            report.add("Investment output", f"{roster.investment_output:.2f}",
                       "Drives how well trades are executed")
        if self._has(AnalyticsTier.ADVANCED):
            happiness = [e.happiness for e in roster]
            if happiness:
                average = sum(float(h) for h in happiness) / len(happiness)
                report.add("Average happiness", f"{average:.0%}",
                           "Unhappy people leave", positive=average >= 0.5)
        if self._has(AnalyticsTier.COMPLETE):
            # V9.10: workforce performance in full.
            training = sum(1 for employee in roster if employee.is_training)
            report.add("In training", str(training),
                       "Not producing while they learn")
            report.add("Management output", f"{roster.management_output:.2f}",
                       "Drives how quickly decisions are approved")
        return report

    # -- the market (V9.7) -------------------------------------------------
    def market_report(self) -> Report | None:
        market = getattr(self.context, "market", None)
        if market is None:
            return None
        report = Report("Market", note="The conditions you are trading into")
        mood = ("Bull market" if market.is_bull_market()
                else "Bear market" if market.is_bear_market() else "Steady")
        report.add("Conditions", mood, "The prevailing mood",
                   positive=None if mood == "Steady" else market.is_bull_market())
        report.add("Index", f"{market.market_index():,.0f}",
                   f"{len(market.active_listings())} companies listed")

        # Bound before either branch: the Complete block below reads it too, and
        # would raise if the trends were ever empty when it ran.
        trends = market.industry_trends
        if self._has(AnalyticsTier.DETAILED) and trends:
            strongest = max(trends, key=lambda industry: trends[industry])
            weakest = min(trends, key=lambda industry: trends[industry])
            report.add("Strongest industry", strongest.value,
                       Percentage(trends[strongest]).format(signed=True),
                       positive=True)
            report.add("Weakest industry", weakest.value,
                       Percentage(trends[weakest]).format(signed=True),
                       positive=False)
        if self._has(AnalyticsTier.COMPLETE):
            # V9.11: what is happening across the market as a whole.
            spread = max(trends.values()) - min(trends.values()) if trends else 0.0
            report.add("Industry spread", Percentage(spread).format(),
                       "Between the strongest and weakest")
            report.add("Total market value", market.total_market_cap().format(decimals=0),
                       "Every listed company combined")
        return report

    # -- investments (V9.8) ------------------------------------------------
    def investment_report(self) -> Report | None:
        company = getattr(self.context, "company", None)
        system = getattr(company, "investments", None) if company else None
        if system is None:
            return None
        stats = system.statistics()
        report = Report("Investments", note="What your holdings have done")
        report.add("Holdings", stats["Holdings value"].format(decimals=0),
                   f"{stats['Open positions']} open")
        unrealised = stats["Unrealised"]
        report.add("Unrealised", unrealised.format(decimals=0, signed=True),
                   "On what you still hold",
                   positive=not unrealised.is_negative)

        if self._has(AnalyticsTier.DETAILED):
            realised = stats["Realised"]
            report.add("Realised", realised.format(decimals=0, signed=True),
                       f"Across {stats['Closed']} closed positions",
                       positive=not realised.is_negative)
            report.add("Win rate", str(stats["Win rate"]),
                       "Share of closed positions in profit")
        return report

    # -- company analytics (V9.9) -----------------------------------------
    def company_intelligence_report(self) -> Report | None:
        """The deepest internal business intelligence (V9.9).

        Its own unlock at the end of the Company branch, rather than a tier of
        the Analytics branch, so it reports on the *organisation* — how each
        department is doing and how efficiently the company runs — where the
        other reports describe position and results.
        """
        if not self.company_analytics:
            return None
        company = getattr(self.context, "company", None)
        roster = getattr(company, "employees", None) if company else None
        if company is None or roster is None:
            return None

        from ..employees import Department

        report = Report("Company intelligence", note="How the organisation performs")
        for department in Department:
            people = roster.in_department(department)
            report.add(str(department), f"{roster.output(department):.2f}",
                       f"{len(people)} assigned")

        finances = company.finances
        salaries = roster.monthly_salary_bill()
        revenue = finances.ledger.lifetime.revenue
        if revenue.is_positive:
            # Operational efficiency: what share of what the company earned went
            # on running it.
            expenses = finances.ledger.lifetime.expenses
            efficiency = 1 - float(expenses.amount / revenue.amount)
            report.add("Operational efficiency", f"{efficiency:.0%}",
                       "Revenue kept after running costs",
                       positive=efficiency > 0)
        report.add("Monthly payroll", salaries.format(decimals=0),
                   f"Across {len(roster)} people")
        return report

    # -- over time (V9.10) -------------------------------------------------
    def historical_report(self) -> Report | None:
        if self.history is None or not self._has(AnalyticsTier.DETAILED):
            return None
        report = Report("Over time", note="How things have changed")
        snapshots = self.history.snapshots
        if not snapshots:
            report.note = "Not enough history yet — come back in a month."
            return report

        latest = snapshots[-1]
        report.add("Net worth", latest.net_worth.format(decimals=0),
                   f"Recorded over {len(snapshots)} month(s)")
        for months, label in ((1, "Last month"), (12, "Last year")):
            change = self.history.change_over("net_worth", months)
            if change is None:
                report.add(label, "—", "Not enough history yet")
            else:
                report.add(label, Percentage(change).format(signed=True),
                           "Change in net worth", positive=change >= 0)
        return report

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "tier": self.tier.name,
            "enabled": self.enabled,
            "company_analytics": self.company_analytics,
        }

    def restore(self, data: dict) -> None:
        self.tier = AnalyticsTier[data.get("tier", "BASIC")]
        self.enabled = bool(data.get("enabled", True))
        self.company_analytics = bool(data.get("company_analytics", False))
