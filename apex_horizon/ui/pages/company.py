"""Company and Financial Management pages.

Design Bible V3.17 makes the Company page where the player spends most of their
management time, and V17.14 requires professional financial reports covering
income, expenses, profit, assets, liabilities, cash flow and net worth.
"""

from __future__ import annotations

import pygame

from ...engine.unlocks import CREATE_COMPANY
from .. import theme
from ..widgets import Button, Card, draw_text, panel
from .base import Page


class CompanyPage(Page):
    """The player's own company (V3.17)."""

    key = "company"
    title = "Company"
    subtitle = "Your investment company"

    def __init__(self, context):
        super().__init__(context)
        self.found_button = Button("Found company", primary=True)
        self.found_requested = False
        self.employees_button = Button("Employee Management", primary=True)
        self.subsidiaries_button = Button("Subsidiaries")
        self.subsidiaries_requested = False
        # Financial Management and Investment Funds are systems of the company,
        # so they are reached from here rather than from the sidebar (V14.5).
        self.finance_button = Button("Financial Management")
        self.funds_button = Button("Investment Funds")
        self.requested_destination: str | None = None
        self.employees_requested = False

    def cards(self):
        company = self.context.company
        player = self.context.player
        if company is None:
            return [
                Card("Personal cash", player.cash.format(decimals=0) if player else "—",
                     "Available to found a company"),
                Card("Founding cost",
                     player.founding_cost.format(decimals=0) if player else "—",
                     "One-off cost to incorporate"),
            ]
        finances = company.finances
        return [
            Card("Company value", company.value().format(decimals=0),
                 f"Level {company.level} of {company.max_level}"),
            Card("Company cash", finances.cash.format(decimals=0),
                 "Available to invest",
                 accent=None if not finances.cash.is_negative else theme.NEGATIVE),
            Card("Last week's profit", finances.last_week.profit.format(
                decimals=0, signed=True),
                "Revenue less expenses",
                accent=theme.value_colour(not finances.last_week.profit.is_negative)),
            Card("Reputation", f"{company.reputation * 100:.0f}%",
                 "Standing in the industry"),
        ]

    def handle_event(self, event) -> bool:
        if (self.context.company is None and self.found_button.enabled
                and self.found_button.handle_event(event)
                and self.found_button.take_click()):
            self.found_requested = True
            return True
        if (self.context.company is not None
                and self.employees_button.handle_event(event)
                and self.employees_button.take_click()):
            self.employees_requested = True
            return True
        if (self.context.company is not None
                and self.subsidiaries_button.handle_event(event)
                and self.subsidiaries_button.take_click()):
            self.subsidiaries_requested = True
            return True
        for button, destination in (
            (self.finance_button, "finance"),
            (self.funds_button, "company:funds"),
        ):
            if (self.context.company is not None and button.handle_event(event)
                    and button.take_click()):
                self.requested_destination = destination
                return True
        return False

    def take_destination_request(self) -> str | None:
        request, self.requested_destination = self.requested_destination, None
        return request

    def take_subsidiaries_request(self) -> bool:
        requested, self.subsidiaries_requested = self.subsidiaries_requested, False
        return requested

    def take_employees_request(self) -> bool:
        requested, self.employees_requested = self.employees_requested, False
        return requested

    def take_found_request(self) -> bool:
        requested, self.found_requested = self.found_requested, False
        return requested

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        company = self.context.company
        if company is None:
            self._draw_no_company(surface, rect, fonts, mouse)
            return

        left = pygame.Rect(rect.left, rect.top, int(rect.width * 0.48), 292)
        panel(surface, left)
        draw_text(surface, fonts.subheading, company.name, (left.left + 20, left.top + 18))
        y = left.top + 56
        for label, value in company.statistics().items():
            draw_text(surface, fonts.small, label, (left.left + 20, y), theme.TEXT_MUTED)
            text = value.format(decimals=0) if hasattr(value, "format") else str(value)
            draw_text(surface, fonts.mono_small, text, (left.right - 20, y),
                      theme.TEXT, align="right")
            y += 25

        right = pygame.Rect(left.right + theme.GAP, rect.top,
                            rect.width - left.width - theme.GAP, 292)
        panel(surface, right)
        draw_text(surface, fonts.subheading, "Organisation", (right.left + 20, right.top + 18))
        roster = company.employees
        y = right.top + 56
        for label, value in roster.statistics().items():
            draw_text(surface, fonts.small, label, (right.left + 20, y), theme.TEXT_MUTED)
            text = value.format(decimals=0) if hasattr(value, "format") else str(value)
            draw_text(surface, fonts.mono_small, text, (right.right - 20, y),
                      theme.TEXT, align="right")
            y += 25
        self.subsidiaries_button.draw(
            surface, pygame.Rect(right.left + 232, right.bottom - 52, 150, 34), fonts, mouse)
        self.finance_button.draw(
            surface, pygame.Rect(right.left + 20, right.bottom - 96, 190, 34), fonts, mouse)
        self.funds_button.draw(
            surface, pygame.Rect(right.left + 232, right.bottom - 96, 150, 34), fonts, mouse)
        self.employees_button.draw(
            surface, pygame.Rect(right.left + 20, right.bottom - 52, 200, 34), fonts, mouse)

        if company.bankrupt:
            draw_text(surface, fonts.small, "This company is bankrupt.",
                      (right.left + 20, right.bottom - 40), theme.NEGATIVE)

    def _draw_no_company(self, surface, rect, fonts, mouse) -> None:
        """The road to a company, shown as steps rather than a locked door.

        Reaching a company takes a long time by design, so this state has to
        read as a plan the player is working through rather than a refusal
        (V14.26). Each step says plainly where the player stands on it.
        """
        player = self.context.player
        box = pygame.Rect(rect.left, rect.top, rect.width, 250)
        panel(surface, box)
        draw_text(surface, fonts.subheading, "You have not founded a company yet",
                  (box.left + 24, box.top + 24))
        draw_text(surface, fonts.small,
                  "You are an individual investor. Build your personal wealth by "
                  "trading, then take these steps when you are ready.",
                  (box.left + 24, box.top + 52), theme.TEXT_MUTED)

        allowed, reason = player.can_found_company() if player else (False, "")
        for index, (label, done, detail) in enumerate(self._founding_steps(player)):
            y = box.top + 92 + index * 30
            marker = "✓" if done else str(index + 1)
            colour = theme.POSITIVE if done else theme.TEXT_FAINT
            draw_text(surface, fonts.small, marker, (box.left + 26, y), colour)
            draw_text(surface, fonts.small, label, (box.left + 48, y),
                      theme.TEXT if done else theme.TEXT_MUTED)
            draw_text(surface, fonts.small, detail, (box.left + 330, y), theme.TEXT_FAINT)

        if not allowed and reason:
            draw_text(surface, fonts.small, reason, (box.left + 24, box.bottom - 62),
                      theme.TEXT_FAINT)
        self.found_button.enabled = allowed
        self.found_button.draw(surface, pygame.Rect(box.right - 194, box.bottom - 56, 170, 38),
                               fonts, mouse)

    def _founding_steps(self, player):
        """The progression V6.4 and V3.3 lay down, with the player's position."""
        if player is None:
            return []
        unlocks = player.unlocks
        cost = unlocks.cost_of(CREATE_COMPANY)
        unlocked = unlocks.has(CREATE_COMPANY)
        return [
            ("Unlock Create Company", unlocked,
             "Unlocked" if unlocked else f"{cost.format(decimals=0)} on the Unlock Tree"),
            ("Afford the founding cost", player.cash >= player.founding_cost,
             f"{player.cash.format(decimals=0)} of "
             f"{player.founding_cost.format(decimals=0)}"),
        ]


class FinancePage(Page):
    """Financial reporting (V17.14)."""

    key = "finance"
    title = "Financial Management"
    subtitle = "Where the company's money comes from and goes"

    def cards(self):
        company = self.context.company
        if company is None:
            return []
        finances = company.finances
        return [
            Card("Net worth", finances.net_worth().format(decimals=0),
                 "Assets less liabilities"),
            Card("Assets", finances.assets().format(decimals=0), "Cash and holdings"),
            Card("Liabilities", finances.liabilities().format(decimals=0),
                 "Outstanding debt"),
            Card("Lifetime profit", finances.lifetime_profit.format(
                decimals=0, signed=True), "Since founding",
                accent=theme.value_colour(not finances.lifetime_profit.is_negative)),
        ]

    def draw_content(self, surface, rect, fonts, mouse) -> None:
        company = self.context.company
        if company is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 160))
            draw_text(surface, fonts.body,
                      "Found a company to begin tracking finances.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        finances = company.finances
        width = (rect.width - theme.GAP * 2) // 3

        report = pygame.Rect(rect.left, rect.top, width, 250)
        panel(surface, report)
        draw_text(surface, fonts.subheading, "This year", (report.left + 20, report.top + 18))
        y = report.top + 56
        for label, value in finances.report(company.level).items():
            draw_text(surface, fonts.small, label, (report.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value.format(decimals=0),
                      (report.right - 20, y), theme.TEXT, align="right")
            y += 24

        spend = pygame.Rect(report.right + theme.GAP, rect.top, width, 250)
        panel(surface, spend)
        draw_text(surface, fonts.subheading, "Where money went",
                  (spend.left + 20, spend.top + 18))
        breakdown = finances.ledger.expense_breakdown()
        y = spend.top + 56
        if not breakdown:
            draw_text(surface, fonts.small, "Nothing spent yet.",
                      (spend.left + 20, y), theme.TEXT_FAINT)
        for label, value in list(breakdown.items())[:7]:
            draw_text(surface, fonts.small, label, (spend.left + 20, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, value.format(decimals=0),
                      (spend.right - 20, y), theme.TEXT, align="right")
            y += 24

        debt = pygame.Rect(spend.right + theme.GAP, rect.top, width, 250)
        panel(surface, debt)
        draw_text(surface, fonts.subheading, "Borrowing", (debt.left + 20, debt.top + 18))
        loans = company.loans.active()
        y = debt.top + 56
        if not loans:
            draw_text(surface, fonts.small, "No outstanding loans.",
                      (debt.left + 20, y), theme.TEXT_FAINT)
        for loan in loans[:5]:
            draw_text(surface, fonts.small, loan.bank_name, (debt.left + 20, y),
                      theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, loan.outstanding.format(decimals=0),
                      (debt.right - 20, y), theme.TEXT, align="right")
            y += 22
            draw_text(surface, fonts.tiny,
                      f"{loan.interest_rate.format()} a year", (debt.left + 20, y),
                      theme.TEXT_FAINT)
            y += 24
