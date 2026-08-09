"""Employee management pages.

Design Bible V5.14 places these behind Company → Employees → Employee
Management, with a list that supports search, pagination, sorting and clickable
rows. V5.15 then defines the details page: statistics, timeline, department
priorities, training, current task, salary, happiness, and hidden
characteristics once they are visible.
"""

from __future__ import annotations

import pygame

from ...engine.employees import ALL_DEPARTMENTS, Department
from ...engine.values import Money
from .. import theme
from ..widgets import Button, Card, Column, Dropdown, SearchBox, Table, draw_text, panel
from .base import Page

DEPARTMENT_NAMES = [str(department) for department in ALL_DEPARTMENTS]


def _department(name: str) -> Department:
    return next(d for d in ALL_DEPARTMENTS if str(d) == name)


class EmployeesPage(Page):
    """The company's staff, and the people applying to join (V5.14, V18.19)."""

    key = "company:employees"
    TITLE = "Employee Management"
    SUBTITLE = "Your staff and the candidates available to you"

    def __init__(self, context):
        super().__init__(context)
        self.search = SearchBox("Search employees")
        self.table = Table(
            columns=[
                Column("name", "Name", 200),
                Column("primary", "Primary", 120),
                Column("skill", "Skill", 70, align="right", numeric=True),
                Column("happiness", "Happiness", 100, align="right", numeric=True,
                       format=lambda v: f"{v * 100:.0f}%"),
                Column("salary", "Salary", 110, align="right", numeric=True,
                       format=lambda v: v.format(decimals=0)),
                Column("task", "Current task", 260),
            ],
            search_key="name",
            sort_key="name",
            page_size=8,
        )
        self.selected_employee_id: str | None = None
        self.recruit_button = Button("Find candidates", primary=True)
        self.hire_buttons: list[tuple[str, Button]] = []
        self.requested_recruit = False
        self.requested_hire: str | None = None

    # -- data --------------------------------------------------------------
    @property
    def roster(self):
        company = self.context.company
        return company.employees if company else None

    def rows(self) -> list[dict]:
        roster = self.roster
        if roster is None:
            return []
        return [
            {
                "id": employee.id,
                "name": employee.name,
                "primary": str(employee.primary),
                "skill": employee.overall_skill,
                "happiness": employee.happiness,
                "salary": employee.salary,
                "task": employee.current_task,
            }
            for employee in roster
        ]

    def breadcrumb(self):
        return [("Company", "company"), ("Employees", self.key)]

    def cards(self):
        roster = self.roster
        if roster is None:
            return []
        stats = roster.statistics()
        cards = [Card("Staff", stats["Employees"], "Against your company level")]
        if len(roster):
            cards.append(Card("Average skill", stats["Average skill"], "Across all three skills"))
            cards.append(Card("Average happiness", stats["Average happiness"],
                              "Pay, workload and success"))
            cards.append(Card("Monthly salaries",
                              roster.monthly_salary_bill().format(decimals=0),
                              "Paid at each month end"))
        return cards

    # -- interaction -------------------------------------------------------
    def handle_event(self, event) -> bool:
        if self.search is not None and self.search.handle_event(event):
            self.table.page = 0
            return True
        if self.table.handle_event(event):
            row = self.table.take_opened()
            if row is not None:
                self.selected_employee_id = row["id"]
                self.navigate_to = "company:employee"
            return True
        if self.recruit_button.handle_event(event) and self.recruit_button.take_click():
            self.requested_recruit = True
            return True
        for employee_id, button in self.hire_buttons:
            if button.handle_event(event) and button.take_click():
                self.requested_hire = employee_id
                return True
        return False

    def take_recruit_request(self) -> bool:
        request, self.requested_recruit = self.requested_recruit, False
        return request

    def take_hire_request(self) -> str | None:
        request, self.requested_hire = self.requested_hire, None
        return request

    # -- drawing -----------------------------------------------------------
    def draw_content(self, surface, rect, fonts, mouse) -> None:
        roster = self.roster
        if roster is None:
            panel(surface, pygame.Rect(rect.left, rect.top, rect.width, 150))
            draw_text(surface, fonts.body, "Found a company before hiring anyone.",
                      (rect.left + 24, rect.top + 60), theme.TEXT_MUTED)
            return

        table_height = min(rect.height - 220, 400)
        self.table.draw(surface, pygame.Rect(rect.left, rect.top, rect.width, table_height),
                        fonts, mouse, self.rows(), self.search.text if self.search else "")
        self._draw_applicants(surface,
                              pygame.Rect(rect.left, rect.top + table_height + theme.GAP,
                                          rect.width, 190),
                              fonts, mouse, roster)

    def _draw_applicants(self, surface, rect, fonts, mouse, roster) -> None:
        """Candidates available to hire (V5.3, V18.14)."""
        panel(surface, rect)
        draw_text(surface, fonts.subheading, "Candidates", (rect.left + 20, rect.top + 16))
        draw_text(surface, fonts.small,
                  "Better candidates appear as your company's reputation grows.",
                  (rect.left + 20, rect.top + 42), theme.TEXT_MUTED)
        self.recruit_button.draw(surface, pygame.Rect(rect.right - 176, rect.top + 16, 156, 32),
                                 fonts, mouse)

        self.hire_buttons.clear()
        if not roster.applicants:
            draw_text(surface, fonts.small, "No candidates right now.",
                      (rect.left + 20, rect.top + 80), theme.TEXT_FAINT)
            return

        y = rect.top + 74
        for applicant in roster.applicants[:4]:
            draw_text(surface, fonts.small, applicant.name, (rect.left + 20, y), theme.TEXT)
            draw_text(surface, fonts.small,
                      f"{applicant.primary} · skill {applicant.overall_skill}",
                      (rect.left + 220, y), theme.TEXT_MUTED)
            draw_text(surface, fonts.mono_small, applicant.salary.format(decimals=0),
                      (rect.left + 460, y), theme.TEXT)
            button = Button("Hire", enabled=not roster.is_full)
            button.draw(surface, pygame.Rect(rect.right - 96, y - 6, 72, 26), fonts, mouse)
            self.hire_buttons.append((applicant.id, button))
            y += 30


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
            Card("Happiness", f"{employee.happiness * 100:.0f}%",
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


def market_rate(employee) -> Money:
    return employee.expected_salary()
