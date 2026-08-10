"""One employee in full.

Split out of the employee pages (2026-08-10) to keep each file within the
size the project works to. The roster this page is opened from lives in
:mod:`.employees`, which this module depends on rather than the reverse.
"""

from __future__ import annotations

import pygame

from ...engine.employees import ALL_DEPARTMENTS, Department
from .. import theme
from ..widgets import Button, Card, Dropdown, draw_text, format_fraction, panel
from .base import Page
from .employees import DEPARTMENT_NAMES, EmployeesPage, _department


class EmployeeDetailPage(Page):
    """One employee in full (V5.15, V5.16)."""

    key = "company:employee"

    def __init__(self, context, employees_page: EmployeesPage):
        super().__init__(context)
        self.employees_page = employees_page
        self.dropdowns: dict[str, Dropdown] = {}
        self.train_buttons: dict[str, Button] = {}
        self.raise_button = Button("Raise to market rate")
        self.dismiss_button = Button("Dismiss")
        self.requested: tuple[str, object] | None = None

    @property
    def employee(self):
        roster = self.employees_page.roster
        if roster is None or self.employees_page.selected_employee_id is None:
            return None
        return roster.by_id(self.employees_page.selected_employee_id)

    @property
    def title(self) -> str:
        employee = self.employee
        return employee.name if employee else "Employee"

    def breadcrumb(self):
        employee = self.employee
        return [
            ("Company", "company"),
            ("Employees", "company:employees"),
            (employee.name if employee else "Employee", self.key),
        ]

    def cards(self):
        employee = self.employee
        if employee is None:
            return []
        return [
            Card("Overall skill", str(employee.overall_skill),
                 f"Ceiling {employee.skill_ceiling}"),
            Card("Happiness", format_fraction(employee.happiness),
                 "Pay, workload and company success",
                 accent=theme.POSITIVE if employee.happiness > 0.6 else (
                     theme.NEGATIVE if employee.happiness < 0.35 else None)),
            Card("Salary", employee.salary.format(decimals=0),
                 f"Expects {employee.expected_salary().format(decimals=0)}"),
            Card("Current task", "Training" if employee.is_training else str(employee.primary),
                 employee.current_task),
        ]

    def on_show(self) -> None:
        self.dropdowns.clear()

    # -- interaction -------------------------------------------------------
    def _dropdown(self, slot: str, selected: Department) -> Dropdown:
        if slot not in self.dropdowns:
            self.dropdowns[slot] = Dropdown(DEPARTMENT_NAMES, str(selected), width=150)
        return self.dropdowns[slot]

    def handle_event(self, event) -> bool:
        employee = self.employee
        if employee is None:
            return False
        for slot, dropdown in self.dropdowns.items():
            if dropdown.handle_event(event):
                changed = dropdown.take_change()
                if changed:
                    self.requested = ("department", (slot, _department(changed)))
                return True
        for department, button in self.train_buttons.items():
            if button.handle_event(event) and button.take_click():
                self.requested = ("train", _department(department))
                return True
        if self.raise_button.handle_event(event) and self.raise_button.take_click():
            self.requested = ("raise", None)
            return True
        if self.dismiss_button.handle_event(event) and self.dismiss_button.take_click():
            self.requested = ("dismiss", None)
            return True
        return False

    def take_request(self):
        request, self.requested = self.requested, None
        return request

    # -- drawing -----------------------------------------------------------
    def draw_content(self, surface, rect, fonts, mouse) -> None:
        employee = self.employee
        if employee is None:
            draw_text(surface, fonts.body, "Select an employee from the list.",
                      (rect.left, rect.top + 20), theme.TEXT_MUTED)
            return

        column = (rect.width - theme.GAP * 2) // 3
        self._draw_skills(surface, pygame.Rect(rect.left, rect.top, column, 300),
                          fonts, mouse, employee)
        self._draw_assignment(
            surface, pygame.Rect(rect.left + column + theme.GAP, rect.top, column, 300),
            fonts, mouse, employee,
        )
        self._draw_timeline(
            surface,
            pygame.Rect(rect.left + (column + theme.GAP) * 2, rect.top, column, 300),
            fonts, employee,
        )

    def _draw_skills(self, surface, rect, fonts, mouse, employee) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Skills", (rect.left + 20, rect.top + 16))
        y = rect.top + 54
        for department in ALL_DEPARTMENTS:
            skill = employee.skill_in(department)
            draw_text(surface, fonts.small, str(department), (rect.left + 20, y),
                      theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, f"{skill}/{employee.skill_ceiling}",
                      (rect.right - 20, y), theme.TEXT, align="right")
            # A bar makes relative strength readable at a glance.
            bar = pygame.Rect(rect.left + 20, y + 20, rect.width - 40, 4)
            pygame.draw.rect(surface, theme.SURFACE_HOVER, bar, border_radius=2)
            filled = pygame.Rect(bar.left, bar.top,
                                 int(bar.width * skill / max(1, employee.skill_ceiling)), 4)
            pygame.draw.rect(surface, theme.ACCENT, filled, border_radius=2)
            y += 44

        draw_text(surface, fonts.small, "Hidden strengths", (rect.left + 20, y + 4),
                  theme.TEXT_MUTED)
        y += 26
        roster = self.employees_page.roster
        if roster is not None and roster.strengths_visible:
            for label, value in employee.hidden.describe().items():
                draw_text(surface, fonts.small, f"{label}: {value}",
                          (rect.left + 20, y), theme.TEXT)
                y += 20
        else:
            # V5.7: hidden until the Recruitment branch reveals them.
            draw_text(surface, fonts.small,
                      "Revealed by the Recruitment unlocks.",
                      (rect.left + 20, y), theme.TEXT_FAINT)

    def _draw_assignment(self, surface, rect, fonts, mouse, employee) -> None:
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Departments", (rect.left + 20, rect.top + 16))
        draw_text(surface, fonts.small,
                  "Best in primary, least in third.",
                  (rect.left + 20, rect.top + 42), theme.TEXT_MUTED)
        y = rect.top + 72
        for slot, current in (("primary", employee.primary),
                              ("secondary", employee.secondary),
                              ("third", employee.third)):
            dropdown = self._dropdown(slot, current)
            dropdown.selected = str(current)
            draw_text(surface, fonts.small, slot.title(), (rect.left + 20, y + 14),
                      theme.TEXT_MUTED, baseline="middle")
            dropdown.draw(surface, pygame.Rect(rect.left + 110, y, 150, 28), fonts, mouse)
            y += 38

        draw_text(surface, fonts.small, "Training", (rect.left + 20, y + 8), theme.TEXT_MUTED)
        y += 32
        self.train_buttons.clear()
        if employee.is_training:
            draw_text(surface, fonts.small, employee.current_task,
                      (rect.left + 20, y), theme.TEXT)
        else:
            for index, department in enumerate(ALL_DEPARTMENTS):
                button = Button(str(department)[:4])
                button.draw(surface,
                            pygame.Rect(rect.left + 20 + index * 78, y, 70, 26), fonts, mouse)
                self.train_buttons[str(department)] = button

        self.raise_button.enabled = employee.salary < employee.expected_salary()
        self.raise_button.draw(surface,
                               pygame.Rect(rect.left + 20, rect.bottom - 44, 180, 30),
                               fonts, mouse)
        self.dismiss_button.draw(surface,
                                 pygame.Rect(rect.right - 100, rect.bottom - 44, 80, 30),
                                 fonts, mouse)

    def _draw_timeline(self, surface, rect, fonts, employee) -> None:
        """The previous ten in-game days (V5.16)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Last ten days", (rect.left + 20, rect.top + 16))
        day = self.context.engine.date.day if self.context.engine else employee.hired_on_day
        entries = list(reversed(employee.recent_timeline(day)))
        y = rect.top + 54
        if not entries:
            draw_text(surface, fonts.small, "Nothing notable this week.",
                      (rect.left + 20, y), theme.TEXT_FAINT)
        for entry in entries[:9]:
            draw_text(surface, fonts.mono_small, entry.marker, (rect.left + 20, y), theme.ACCENT)
            draw_text(surface, fonts.small, entry.text, (rect.left + 40, y), theme.TEXT_MUTED)
            y += 24

    def draw_overlays(self, surface, fonts, mouse) -> None:
        """Open dropdown lists, drawn above the page (V14 layering)."""
        for dropdown in self.dropdowns.values():
            dropdown.draw_open(surface, fonts, mouse)
