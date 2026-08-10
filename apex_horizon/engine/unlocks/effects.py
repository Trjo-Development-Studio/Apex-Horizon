"""What each unlock actually does.

V6.3 is firm: every unlock must provide a noticeable improvement or introduce a
completely new gameplay system, and the player should never unlock something
that feels insignificant. This module is where that promise is kept — one place
that reads the tree and configures the systems accordingly.

It is deliberately a *pusher* rather than a set of hooks. Systems do not ask the
tree what the player owns; the tree tells them what they are. That keeps every
gameplay system ignorant of progression (V15.7) — the market does not know the
Unlock Tree exists, the roster only knows it has a recruitment tier — and it
means effects can be re-applied wholesale after loading a save, rather than
being scattered through the code that grants them.

Every figure comes from configuration (V15.10), so the whole progression curve
is tunable without touching this file.
"""

from __future__ import annotations

from ..config import Config, get_config
from ..logging_setup import get_logger
from . import catalogue as c

logger = get_logger(__name__)


class UnlockEffects:
    """Applies the consequences of what the player has unlocked."""

    def __init__(self, tree, *, config: Config | None = None):
        self.config = config or get_config()
        self.tree = tree

    def apply(self, context) -> None:
        """Configure every system to match what is currently unlocked.

        Safe to call at any time, and called after loading so a restored game
        behaves exactly like the one that was saved.
        """
        self._apply_news(getattr(context, "news", None))
        self._apply_analytics(getattr(context, "analytics", None))
        company = getattr(context, "company", None)
        if company is not None:
            self._apply_company(company)
            self._apply_employees(getattr(company, "employees", None))

    # -- News branch (V6.6.2, V10.4) --------------------------------------
    def _apply_news(self, news) -> None:
        if news is None:
            return
        from ..news import NewsTier

        reached = self.tree.highest(
            c.BASIC_NEWS, c.MARKET_NEWS, c.ECONOMIC_NEWS, c.BREAKING_NEWS
        )
        # Without Basic News the player has no financial press at all; the tier
        # ladder then follows the branch exactly (V10.4).
        news.enabled = reached > 0
        if reached:
            news.tier = (NewsTier.BASIC, NewsTier.MARKET,
                         NewsTier.ECONOMIC, NewsTier.BREAKING)[reached - 1]

    # -- Analytics branch (V6.6.1, V9.6) and Company Analytics (V9.9) -----
    def _apply_analytics(self, analytics) -> None:
        if analytics is None:
            return
        from ..analytics import AnalyticsTier

        reached = self.tree.highest(
            c.BASIC_ANALYTICS, c.BETTER_ANALYTICS_1,
            c.BETTER_ANALYTICS_2, c.BETTER_ANALYTICS_3,
        )
        analytics.enabled = reached > 0
        if reached:
            analytics.tier = (AnalyticsTier.BASIC, AnalyticsTier.DETAILED,
                              AnalyticsTier.ADVANCED, AnalyticsTier.COMPLETE)[reached - 1]
        # V9.9: the deepest internal business intelligence, from its own branch.
        analytics.company_analytics = self.tree.has(c.COMPANY_ANALYTICS)

    # -- Company branch (V6.7.3, V3.7) ------------------------------------
    def _apply_company(self, company) -> None:
        level = 1 + self.tree.highest(
            c.COMPANY_LEVEL_2, c.COMPANY_LEVEL_3, c.COMPANY_LEVEL_4, c.COMPANY_LEVEL_5
        )
        if company.level != level:
            company.set_level(level)
        # Borrowing is what the Finance branch opens (V6.7.1, V6.16).
        company.borrowing_allowed = self.tree.has(c.FINANCE)
        company.finance_tier = self.tree.highest(
            c.BETTER_FINANCE_1, c.BETTER_FINANCE_2, c.BETTER_FINANCE_3
        )
        # The final unlock opens institutional capital (V11.3, V6.8).
        if company.funds is not None:
            company.funds.unlocked = self.tree.has(c.INVESTMENT_FUNDS)

    # -- Employee, Training and Recruitment branches (V6.7.2, .4, .5) -----
    def _apply_employees(self, roster) -> None:
        if roster is None:
            return
        # Skill ceilings follow the Better Employees levels exactly: 20, 30, 40
        # (V6.7.2). Hiring itself is never gated — the project manager ruled it
        # available from founding, matching V1.19's example of hiring straight
        # after founding a company.
        roster.recruitment_tier = self.tree.highest(
            c.BETTER_EMPLOYEES_1, c.BETTER_EMPLOYEES_2, c.BETTER_EMPLOYEES_3
        )

        # Training is gated (project manager's ruling), and improves with the
        # branch (V6.7.4).
        roster.training_allowed = self.tree.has(c.EMPLOYEE_TRAINING)
        speeds = self.config.get_list("unlocks.training_speed_multipliers")
        training_level = self.tree.highest(
            c.BETTER_TRAINING_1, c.BETTER_TRAINING_2, c.BETTER_TRAINING_3
        )
        roster.training_speed = float(
            speeds[min(training_level, len(speeds) - 1)] if speeds else 1.0
        )

        # Recruitment branch (V6.7.5).
        pools = self.config.get_list("unlocks.applicant_pool_by_level")
        pool_level = self.tree.highest(c.MORE_APPLICANTS)
        roster.applicant_pool = int(
            pools[min(pool_level, len(pools) - 1)] if pools else 5
        )
        weights = self.config.get_list("unlocks.reputation_weight_by_level")
        recruitment_level = self.tree.highest(c.BETTER_RECRUITMENT)
        roster.reputation_weight = float(
            weights[min(recruitment_level, len(weights) - 1)] if weights else 0.5
        )
        roster.strengths_visible = self.tree.has(c.EMPLOYEE_STRENGTHS)
        roster.performance_visible = self.tree.has(c.EMPLOYEE_PERFORMANCE)
        roster.automation_allowed = self.tree.has(c.AUTOMATED_RECRUITMENT)
