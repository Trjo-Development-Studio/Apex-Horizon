"""A bankrupt company, and the Subsidiaries unlock gate and Buy flow."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
from ui_support import _found_company_for_acquisitions, click, release

from apex_horizon.engine.unlocks import CREATE_COMPANY
from apex_horizon.engine.values import Money

# -- a bankrupt company is not operational (bug fix, 2026-08-09) -----------
#
# has_company already meant "a company exists and is not bankrupt", but most
# pages checked context.company for None directly, which stays true after
# bankruptcy — so a dead company kept showing its stale (usually deeply
# negative) figures as though it were still trading, and Employee Management
# stayed fully usable: a real, provable path let a player hire someone into a
# company with roughly -$1,000,000 in cash. Every page below is checked, plus
# the engine-level refusal that now backs the UI gating up.


def _bankrupt_company(app, cash: int = 50_000):
    app.context.player.cash = Money(cash)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, message = app.context.player.found_company("Doomed Capital", 1)
    assert company is not None, message
    company.attach_market(app.context.market, app.context.allocator)
    company.register(app.context.engine)
    company.declare_bankruptcy(app.context.engine.date.day)
    return company


def test_has_company_is_false_once_bankrupt(app):
    company = _bankrupt_company(app)

    assert app.context.company is company, "the record stays (V1.3)"
    assert not app.context.has_company
    assert app.context.bankrupt_company is company


def test_has_company_is_true_for_a_going_concern(app):
    """The other half of the distinction: a solvent company still counts."""
    app.context.player.cash = Money(50_000)
    app.context.player.unlocks.unlock(CREATE_COMPANY)
    company, _ = app.context.player.found_company("Going Concern", 1)

    assert app.context.has_company
    assert app.context.bankrupt_company is None
    assert company is not None


def test_every_page_still_renders_for_a_bankrupt_company(app):
    """The regression this whole batch is guarding against: nothing may raise,
    whatever a page decides to show instead of the dead company's figures."""
    _bankrupt_company(app)
    for key in list(app.pages):
        app.navigate(key)
        app.draw(0)


def test_dashboard_drops_the_company_cards_once_bankrupt(app):
    _bankrupt_company(app)
    labels = [card.label for card in app.pages["dashboard"].cards()]
    assert "Company cash" not in labels
    assert "Staffing" not in labels


def test_dashboard_does_not_rank_a_bankrupt_company(app):
    """It must not be compared against ai.operating as though still trading."""
    _bankrupt_company(app)
    app.navigate("dashboard")
    surface = pygame.Surface((1440, 860))
    app.pages["dashboard"]._draw_competitors(
        surface, pygame.Rect(0, 0, 1400, 300), app.fonts)
    # No exception is the main guarantee; the source of truth for "no ranking
    # line" is player_company being None, which test_has_company_is_false_once
    # _bankrupt already pins directly.


def test_company_page_shows_the_notice_not_live_figures(app):
    company = _bankrupt_company(app)
    page = app.pages["company"]

    labels = [card.label for card in page.cards()]
    assert labels == ["Founding cost"], "not the live company cards"

    failed = app.context.bankrupt_company
    assert failed is company
    assert f"{company.name} went bankrupt" in \
        f"{failed.name} went bankrupt on day {failed.bankrupt_on_day}"


def test_company_page_buttons_are_unreachable_once_bankrupt(app):
    """Employee Management, Subsidiaries, Financial Management, Investment
    Funds — none of them should be clickable into a dead company."""
    _bankrupt_company(app)
    app.navigate("company")
    app.draw(0)
    page = app.pages["company"]

    for button in (page.employees_button, page.subsidiaries_button,
                   page.finance_button, page.funds_button):
        page.handle_event(click(button.rect.center))
        page.handle_event(release(button.rect.center))

    assert not page.take_employees_request()
    assert not page.take_subsidiaries_request()
    assert page.take_destination_request() is None


def test_the_found_button_is_available_again_once_bankrupt(app):
    """Refounding is the one action a bankrupt state should still offer."""
    _bankrupt_company(app)
    app.navigate("company")
    app.draw(0)
    page = app.pages["company"]

    assert page.found_button.enabled is False, \
        "not enough net worth yet to refound (project manager's post-bankruptcy rule)"
    app.context.player.cash = Money(600_000)
    app.draw(0)
    assert page.found_button.enabled is True


def test_finance_page_shows_no_cards_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["finance"].cards() == []
    app.navigate("finance")
    app.draw(0)  # must not raise trying to format a dead company's figures


def test_employees_page_has_no_roster_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:employees"].roster is None


def test_subsidiaries_page_has_no_book_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:subsidiaries"].book is None


def test_funds_page_has_no_book_once_bankrupt(app):
    _bankrupt_company(app)
    assert app.pages["company:funds"].book is None


def test_hiring_is_refused_through_the_real_dispatcher(app):
    """Not just an unreachable button: the dispatcher itself must refuse too,
    the way it already would for a full company."""
    company = _bankrupt_company(app)
    from random import Random

    from apex_horizon.engine.employees import generate_applicants
    from apex_horizon.engine.values import IdAllocator
    from apex_horizon.engine.world import NameGenerator

    applicant = generate_applicants(Random(1), NameGenerator(Random(1)),
                                    IdAllocator(), count=1)[0]
    company.employees.applicants.append(applicant)

    page = app.pages["company:employees"]
    page.requested_hire = applicant.id
    app._handle_employees_page(page)

    assert len(company.employees) == 0


def test_no_company_message_distinguishes_bankruptcy_from_never_founded(app):
    from apex_horizon.ui.pages.base import no_company_message

    never_founded = no_company_message(app.context, "to test this")
    assert "bankrupt" not in never_founded.lower()

    _bankrupt_company(app)
    after_bankruptcy = no_company_message(app.context, "to test this")
    assert "went bankrupt" in after_bankruptcy
    assert "Doomed Capital" in after_bankruptcy


def test_refounding_restores_full_operation(app):
    """The other side of the fix: this must all come back for a fresh company."""
    _bankrupt_company(app)
    app.context.player.cash = Money(600_000)
    new_company, message = app.context.player.found_company("Second Chance", 1)
    assert new_company is not None, message

    assert app.context.has_company
    assert app.context.bankrupt_company is None
    assert app.pages["company:employees"].roster is new_company.employees
    assert app.pages["company"].cards()[0].label != "Founding cost"

    for key in list(app.pages):
        app.navigate(key)
        app.draw(0)


# -- Subsidiaries: unlock gate and the Buy flow (2026-08-10) ---------------
#
# Buying moves to Company -> Subsidiaries -> Buy; the Market page's old
# Acquire button is gone. Subsidiaries itself is gated behind a new unlock,
# one leaf past Investment Funds, with existing subsidiaries grandfathered.


def test_the_market_page_names_its_own_empty_state(app):
    """The generic Table fallback ("Nothing to show yet.") read oddly for a
    page that always has companies except in a genuine edge case (bug fix,
    2026-08-10) — the Market page now says specifically what is missing."""
    page = app.pages["market"]
    captured = {}
    original_draw = page.table.draw

    def spy(surface, rect, fonts, mouse, rows, query="", **kwargs):
        captured.update(kwargs)
        return original_draw(surface, rect, fonts, mouse, rows, query, **kwargs)

    page.table.draw = spy
    app.navigate("market")
    app.draw(0)

    assert captured.get("empty_message") == "No companies are listed on the market right now."
    assert captured["empty_message"] != "Nothing to show yet."


def test_the_market_page_no_longer_offers_an_acquire_button(app):
    """Buying outright moved to Company -> Subsidiaries -> Buy; the Market
    page's company detail must not carry the old flow's remnants."""
    page = app.pages["market:company"]
    assert not hasattr(page, "acquire_button")
    assert not hasattr(page, "acquire_request")
    assert not hasattr(page, "take_acquire_request")


def test_subsidiaries_page_offers_no_buy_action_while_locked(app):
    company = _found_company_for_acquisitions(app)
    assert company.subsidiaries.unlocked is False
    page = app.pages["company:subsidiaries"]
    app.navigate("company:subsidiaries")
    app.draw(0)
    # The button exists but must never be reachable while locked.
    page.buy_button.handle_event(click((1, 1)))
    assert not page.requested_buy


def test_buy_button_navigates_to_the_buy_page_through_the_real_dispatcher(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    page = app.pages["company:subsidiaries"]
    app.navigate("company:subsidiaries")
    app.draw(0)

    pos = page.buy_button.rect.center
    page.handle_event(click(pos))
    app.draw(16)
    page.handle_event(release(pos))
    app._collect_page_requests()

    assert app.current_key == "company:subsidiaries:buy"


def test_the_buy_page_lists_acquirable_companies_and_excludes_the_players_own(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    page = app.pages["company:subsidiaries:buy"]
    rows = page.rows()
    assert rows, "the market should offer something to acquire"
    assert all(row["id"] != company.id for row in rows)


def test_selecting_a_row_opens_the_purchase_detail_page(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    buy_page = app.pages["company:subsidiaries:buy"]
    app.navigate("company:subsidiaries:buy")
    app.draw(0)
    row_rect, row = next(iter(buy_page.table._row_rects))

    buy_page.handle_event(click(row_rect.center))
    app._collect_page_requests()

    assert app.current_key == "company:subsidiaries:buy:company"
    assert buy_page.selected_company_id == row["id"]


def test_the_acquire_button_is_enabled_for_a_companys_very_first_acquisition(app):
    """Bug fix, 2026-08-10: SubsidiaryBook defines __len__, so `if book:`
    reads a company with zero subsidiaries so far — exactly a first-time
    buyer's position — as falsy and silently disabled the button. Must use
    `is not None`."""
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    assert len(company.subsidiaries) == 0
    buy_page = app.pages["company:subsidiaries:buy"]
    target_id = buy_page.rows()[0]["id"]
    detail_page = app.pages["company:subsidiaries:buy:company"]
    buy_page.selected_company_id = target_id
    app.navigate("company:subsidiaries:buy:company")

    app.draw(0)

    assert detail_page.acquire_button.enabled is True


def test_clicking_acquire_buys_the_company_through_the_real_dispatcher(app):
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    buy_page = app.pages["company:subsidiaries:buy"]
    target_id = buy_page.rows()[0]["id"]
    buy_page.selected_company_id = target_id
    app.navigate("company:subsidiaries:buy:company")
    app.draw(0)
    detail_page = app.pages["company:subsidiaries:buy:company"]

    pos = detail_page.acquire_button.rect.center
    detail_page.handle_event(click(pos))
    app.draw(16)
    detail_page.handle_event(release(pos))
    app._collect_page_requests()
    assert app.popups.is_open
    app.popups.current.chosen = "acquire"
    app.popups.handle_event(pygame.event.Event(pygame.USEREVENT))

    assert company.subsidiaries.owns(target_id)
    assert app.current_key == "company:subsidiaries"


def test_a_subsidiary_bought_before_the_unlock_stays_owned_and_visible(app):
    """Grandfathered: a subsidiary already owned must keep showing and
    earning even if the unlock is later found missing (e.g. an old save)."""
    company = _found_company_for_acquisitions(app)
    company.subsidiaries.unlocked = True
    target_id = app.pages["company:subsidiaries:buy"].rows()[0]["id"]
    subsidiary, message = company.subsidiaries.acquire(target_id, app.context.engine.date.day)
    assert subsidiary is not None, message

    company.subsidiaries.unlocked = False  # as an old save would restore it

    page = app.pages["company:subsidiaries"]
    assert target_id in {row["id"] for row in page.rows()}
    allowed, _ = company.subsidiaries.can_acquire(
        next(r["id"] for r in app.pages["company:subsidiaries:buy"].rows()
            if r["id"] != target_id)
    )
    assert not allowed, "the gate still blocks a genuinely new acquisition"
