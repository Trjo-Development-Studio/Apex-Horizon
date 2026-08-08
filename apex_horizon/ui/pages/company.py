"""Company and Financial Management pages.

Design Bible V3.17 makes the Company page where the player spends most of their
management time, and V17.14 requires professional financial reports covering
income, expenses, profit, assets, liabilities, cash flow and net worth.
"""

from __future__ import annotations

import pygame

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
        return False

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

        left = pygame.Rect(rect.left, rect.top, int(rect.width * 0.48), 268)
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
                            rect.width - left.width - theme.GAP, 268)
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
        self.employees_button.draw(
            surface, pygame.Rect(right.left + 20, right.bottom - 52, 200, 34), fonts, mouse)

        if company.bankrupt:
            draw_text(surface, fonts.small, "This company is bankrupt.",
                      (right.left + 20, right.bottom - 40), theme.NEGATIVE)

    def _draw_no_company(self, surface, rect, fonts, mouse) -> None:
        player = self.context.player
        box = pygame.Rect(rect.left, rect.top, rect.width, 210)
        panel(surface, box)
        draw_text(surface, fonts.subheading, "You have not founded a company yet",
                  (box.left + 24, box.top + 26))
        allowed, reason = player.can_found_company() if player else (False, "")
        message = (
            "Founding your investment company is the first real decision of a "
            "playthrough, and it is deliberately yours to time."
            if allowed else reason
        )
        draw_text(surface, fonts.small, message, (box.left + 24, box.top + 62),
                  theme.TEXT_MUTED)
        self.found_button.enabled = allowed
        self.found_button.draw(surface, pygame.Rect(box.left + 24, box.top + 112, 170, 38),
                               fonts, mouse)


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
