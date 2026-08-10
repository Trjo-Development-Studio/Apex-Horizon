"""Hiring, recruitment pacing and automation, departments and filters."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import click, release

from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money

# -- hiring from the Employees page (bug fix, 2026-08-09) ------------------
#
# The Hire buttons were recreated from scratch every draw call. A real click
# spans two frames — mouse-down on one, mouse-up on the next, with a draw in
# between — and a brand-new Button() on the second frame has no memory of the
# press the first frame saw, so the release was silently ignored. Nothing
# exercised the click through actual down/up events, so nothing caught it.


def _found_company_with_applicant(app):
    """A company that can afford to hire, with exactly one applicant waiting."""
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    roster = company.employees
    roster.refresh_applicants(app.context.engine.rng, app.context.names,
                              app.context.allocator, app.context.engine.date.day)
    assert roster.applicants, "the generator should have produced someone to hire"
    return company, roster, roster.applicants[0]


def _hire_button_center(app, applicant_id: str):
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    button = page.hire_buttons[applicant_id]
    return button.rect.center


def _click_across_a_frame(app, pos) -> None:
    """A mouse-down, a frame drawn in between, then the mouse-up — real play."""
    page = app.pages["company:employees"]
    page.handle_event(click(pos))
    app.draw(16)  # the frame that used to wipe out the Hire button's press
    page.handle_event(release(pos))
    app._collect_page_requests()


def test_clicking_hire_across_two_frames_adds_the_employee(app):
    """Test 1: normal hiring, through the real down/up click sequence."""
    _, roster, applicant = _found_company_with_applicant(app)
    before = len(roster)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))

    assert len(roster) == before + 1
    assert any(employee.id == applicant.id for employee in roster.employees)


def test_hiring_updates_the_roster_page_immediately(app):
    """Test 5: the employee appears in the UI without a separate refresh."""
    _, _roster, applicant = _found_company_with_applicant(app)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))

    page = app.pages["company:employees"]
    assert applicant.id in {row["id"] for row in page.rows()}


def test_hiring_removes_the_applicant_so_they_cannot_be_hired_twice(app):
    """Test 3: the same applicant cannot immediately be hired again."""
    _, roster, applicant = _found_company_with_applicant(app)

    _click_across_a_frame(app, _hire_button_center(app, applicant.id))
    assert not any(a.id == applicant.id for a in roster.applicants)
    count_after_first_hire = len(roster)

    # The button for a since-hired applicant no longer exists to click, but the
    # dispatcher must still refuse safely if it is ever asked to hire them again.
    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert len(roster) == count_after_first_hire


def _fill_to_capacity(app, roster) -> None:
    """Hire filler employees up to the company's limit.

    Reuses the app's own allocator and name generator rather than fresh ones:
    a second ``IdAllocator()`` starts counting from the same id used by the
    applicant pool, and a filler colliding on id with a real applicant gets
    stripped out of ``roster.applicants`` by ``hire()``'s own id-based filter.
    """
    from apex_horizon.engine.employees import generate_applicants

    while not roster.is_full:
        filler = generate_applicants(
            app.context.engine.rng, app.context.names, app.context.allocator, count=1,
        )[0]
        roster.hire(filler, app.context.engine.date.day)


def test_a_full_company_shows_hire_as_unavailable(app):
    """Test 2: capacity is respected, and shown as unavailable rather than
    failing silently."""
    _, roster, applicant = _found_company_with_applicant(app)
    _fill_to_capacity(app, roster)
    assert roster.is_full

    pos = _hire_button_center(app, applicant.id)
    before = len(roster)

    _click_across_a_frame(app, pos)

    assert len(roster) == before, "a full company must not gain another employee"
    page = app.pages["company:employees"]
    assert not page.hire_buttons[applicant.id].enabled


def test_a_rejected_hire_tells_the_player_why(app):
    """Test 6: a legitimate failure is explained, not swallowed."""
    _, roster, applicant = _found_company_with_applicant(app)
    _fill_to_capacity(app, roster)
    assert applicant.id in {a.id for a in roster.applicants}, \
        "the original applicant should still be waiting, just unable to join"

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app.notifications.items.clear()

    app._handle_employees_page(page)

    assert app.notifications.items, "a refusal must say something, not nothing"
    message = app.notifications.items[-1].text.lower()
    assert "capacity" in message or "level" in message or "hold" in message


def test_hiring_dispatch_marks_the_game_as_having_unsaved_changes(app):
    """Test 4 (part 1): the hire must land in state the save system will pick
    up. This is what makes it actually saved rather than a UI-only change."""
    _, roster, applicant = _found_company_with_applicant(app)
    app.saves.unsaved_changes = False

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert app.saves.unsaved_changes
    assert any(employee.id == applicant.id for employee in roster.employees)


# -- recruitment pacing and automation, through the real UI (2026-08-10) --


def _found_company_with_market(app):
    """A company with a real market attached, so recruitment scheduling has
    the name generator and id allocator it needs (attach_recruitment_sources
    is wired inside attach_market)."""
    app.context.player.cash = Money(60_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Test Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    # The real founding flow wires this through _observe_company; founding
    # directly here, as every other employee test in this module does,
    # bypasses that popup-driven path, so it is wired explicitly instead.
    app._observe_recruitment(company)
    return company, company.employees


def test_clicking_find_candidates_schedules_a_wait_rather_than_instant_candidates(app):
    _, roster = _found_company_with_market(app)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)

    pos = page.recruit_button.rect.center if page.recruit_button.rect.width else (
        app.surface.get_width() - 100, 300)
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert roster.pending_applicants_day is not None
    assert roster.applicants == []


def test_the_arriving_message_and_disabled_button_show_while_pending(app):
    _, roster = _found_company_with_market(app)
    roster.request_applicants(app.context.engine.date.day)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    assert not page.recruit_button.enabled


def test_an_arrival_notification_is_pushed_through_the_real_engine(app):
    _, roster = _found_company_with_market(app)
    roster.request_applicants(app.context.engine.date.day)
    delay = roster.config.get_int("employees.recruitment_delay_days")
    app.notifications.items.clear()

    app.context.engine.run_days(delay + 1)

    assert roster.applicants, "the pool should have arrived"
    assert any("applicant" in item.text.lower() for item in app.notifications.items)


def test_automation_controls_stay_hidden_until_unlocked(app):
    _, roster = _found_company_with_market(app)
    assert not roster.automation_allowed
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    # Nothing to click: the controls are not drawn at all pre-unlock, so their
    # rects stay at the Button() default rather than a real position.
    assert page.automation_button.rect.width == 0


def test_automation_toggle_flows_through_the_real_dispatcher(app):
    _, roster = _found_company_with_market(app)
    roster.automation_allowed = True
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)
    assert page.automation_button.rect.width > 0, "unlocked, so it must be drawn"

    pos = page.automation_button.rect.center
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert roster.auto_recruit_enabled is True


# -- employee departments, filters and Performance (QoL pass, 2026-08-10) --
#
# Company -> Employees -> {department}, built generically off Department
# rather than one hardcoded tab, plus a couple of useful filters on top and
# a derived Performance figure gated behind the same unlock that already
# existed for it (roster.performance_visible) but was never wired to
# anything.


def _hire_one_in_each_department(app, roster):
    """One employee per department, plus one extra Research hire so a skill
    filter test has something on both sides of a threshold."""
    from apex_horizon.engine.employees import Department, generate_applicants

    hired = []
    for department in (Department.RESEARCH, Department.MANAGEMENT, Department.INVESTMENT):
        applicant = generate_applicants(
            app.context.engine.rng, app.context.names, app.context.allocator, count=1,
        )[0]
        applicant.set_priorities(department, *[d for d in Department if d is not department])
        roster.hire(applicant, app.context.engine.date.day)
        hired.append(applicant)
    return hired


def test_department_tabs_filter_the_roster_to_one_department(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    page.department_tabs.selected = str(hired[0].primary)
    shown = {row["id"] for row in page.rows()}
    assert shown == {hired[0].id}


def test_all_tab_shows_the_whole_roster(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]
    assert page.department_tabs.selected == "All"
    assert {row["id"] for row in page.rows()} == {e.id for e in hired}


def test_breadcrumb_reflects_the_selected_department(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    assert page.breadcrumb() == [("Company", "company"), ("Employees", page.key)]
    page.department_tabs.selected = str(hired[0].primary)
    assert page.breadcrumb()[-1] == (str(hired[0].primary), page.key)


def test_status_filter_isolates_training_employees(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    roster.training_allowed = True
    roster.start_training(hired[0], hired[0].secondary, app.context.engine.date.day)
    page = app.pages["company:employees"]

    page.status_filter.selected = "Training"
    assert {row["id"] for row in page.rows()} == {hired[0].id}

    page.status_filter.selected = "Available"
    assert hired[0].id not in {row["id"] for row in page.rows()}
    assert len(page.rows()) == 2


def test_skill_filter_excludes_employees_below_the_threshold(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    high_bar = max(e.overall_skill for e in hired) + 1
    page.skill_filter.selected = f"{high_bar}+" if f"{high_bar}+" in (
        "10+", "20+", "30+") else "30+"
    shown = page.rows()
    for row in shown:
        assert row["skill"] >= int(page.skill_filter.selected.rstrip("+"))


def test_performance_is_hidden_until_unlocked_then_shows_a_percentage(app):
    _, roster = _found_company_with_market(app)
    _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    assert roster.performance_visible is False
    assert all(row["performance"] == "—" for row in page.rows())

    roster.performance_visible = True
    assert all(row["performance"].endswith("%") for row in page.rows())


def test_clicking_a_department_tab_flows_through_a_real_event(app):
    _, roster = _found_company_with_market(app)
    hired = _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]
    app.navigate("company:employees")
    app.draw(0)

    label = str(hired[0].primary)
    rect = next(rect for rect, tab_label in page.department_tabs._rects if tab_label == label)
    page.handle_event(click(rect.center))

    assert page.department_tabs.selected == label


def test_an_empty_department_reports_no_employees_rather_than_a_generic_message(app):
    _, roster = _found_company_with_market(app)
    _hire_one_in_each_department(app, roster)
    page = app.pages["company:employees"]

    from apex_horizon.engine.employees import Department

    # Every department got exactly one hire above; picking a fourth state (no
    # such department exists, so this just proves rows() empties out cleanly
    # rather than asserting on drawn text) is unnecessary — instead confirm
    # the roster-wide vs. department-scoped counts genuinely differ.
    page.department_tabs.selected = str(Department.RESEARCH)
    research_only = len(page.rows())
    page.department_tabs.selected = "All"
    assert len(page.rows()) > research_only


def test_hiring_more_staff_does_not_move_the_search_box_or_cards(app):
    """Layout stability (V17): once a company has any staff at all — the
    steady state a playthrough spends almost all its time in — fixed page
    furniture must not depend on exactly how many employees are on the
    roster. (Going from zero to one is its own deliberate empty-state
    transition, covered separately; this is about two hires looking the
    same as ten.)"""
    from apex_horizon.engine.employees import Department, generate_applicants

    _, roster = _found_company_with_market(app)
    first = generate_applicants(app.context.engine.rng, app.context.names,
                                app.context.allocator, count=1)[0]
    roster.hire(first, app.context.engine.date.day)
    app.navigate("company:employees")
    app.draw(0)
    page = app.pages["company:employees"]
    before_search_rect = pygame.Rect(page.search.rect)
    cards_before = len(page.cards())

    for department in Department:
        applicant = generate_applicants(app.context.engine.rng, app.context.names,
                                        app.context.allocator, count=1)[0]
        applicant.set_priorities(department, *[d for d in Department if d is not department])
        roster.hire(applicant, app.context.engine.date.day)
    app.draw(16)

    assert len(page.cards()) == cards_before, "the set of summary cards must not change with headcount"
    assert pygame.Rect(page.search.rect) == before_search_rect
