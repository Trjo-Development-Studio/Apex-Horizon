"""How one AI company decides what to do.

V26.10 is the rule that shapes this module: an AI company is an instance of the
*same* structure as the player's, differing only in that its strategic
decisions — hiring, department assignment, what to do with spare cash — are
generated procedurally rather than taken by a person. So there is no AI company
class here. There is a director, and it operates an ordinary
:class:`~apex_horizon.engine.company.InvestmentCompany`.

Everything else the AI does is not written here at all, because it is already
written elsewhere: investing runs through the identical workflow of V8.3
(V26.7), the market sees its orders as ordinary demand (V26.8, V4.8), and its
solvency follows the same financial rules the player's company obeys (V17.18).
That reuse is the point — V26.10 asks for it explicitly so AI companies stay
compatible with every future change to company-level systems (V15.7).

What makes one AI company differ from another is not a setting on the director
but who it happened to hire (V26.3). Their hidden characteristics — investment
size, risk tolerance, style, market focus (V5.7) — decide how it invests, and
because AI staff are drawn with a bias toward higher risk (V26.4) the population
skews bolder than the player without any company being scripted to be reckless.
"""

from __future__ import annotations

from decimal import Decimal
from random import Random

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import SimulationContext
from ..values import Money

logger = get_logger(__name__)


class AIDirector:
    """Runs one AI company: the decisions a player would otherwise make."""

    def __init__(self, company, *, rng: Random, config: Config | None = None):
        self.config = config or get_config()
        self.company = company
        self.rng = rng
        self._last_reviewed_day: int | None = None

    # -- the day -----------------------------------------------------------
    def review(self, context: SimulationContext, names, allocator) -> None:
        """Consider hiring, and keep the organisation staffed.

        Guarded against running twice for a day, like every other handler
        (V15.26). Investing is not driven from here: the company's own
        investment system does that on the same schedule the player's does.
        """
        if self._last_reviewed_day == context.day_number:
            return
        self._last_reviewed_day = context.day_number
        if self.company.bankrupt:
            return

        interval = self.config.get_int("ai.hiring_review_days")
        if interval <= 0 or context.day_number % interval:
            return
        self._consider_growth()
        self._consider_hiring(context, names, allocator)

    def _consider_growth(self) -> None:
        """Grow the organisation as it becomes worth more (V26.5, V18.17).

        The player raises Company Level by buying unlocks; an AI company has no
        Unlock Tree, so the same progression is reached procedurally from what
        the company is actually worth. V26.5 asks for growth to be an emergent
        outcome rather than a scripted plan, which is what tying it to value
        does: a company that invests well grows, and one that does not stays
        small.
        """
        thresholds = self.config.get_list("ai.level_value_thresholds")
        if not thresholds:
            return
        value = self.company.value().amount
        earned = 1
        for index, threshold in enumerate(thresholds, start=2):
            if value >= Decimal(str(threshold)):
                earned = index
        if earned > self.company.level:
            self.company.set_level(earned)

    def _consider_hiring(self, context: SimulationContext, names, allocator) -> None:
        """Hire when there is room, work to be done, and money to pay for it.

        V18.16 has AI companies managing employees as the player does, so the
        test is the same one a player applies: can the company afford this
        person for long enough to be worth hiring?
        """
        roster = self.company.employees
        if len(roster) >= roster.capacity:
            return

        # Money is Decimal-backed (V30.2), so the runway is converted rather
        # than multiplied in as a float.
        months = Decimal(str(self.config.get_float("ai.salary_runway_months")))
        payroll = roster.monthly_salary_bill()
        cash = self.company.finances.cash
        if len(roster) and cash < Money(payroll.amount * months):
            # Already stretched; grow no further until the money recovers.
            return

        roster.refresh_applicants(self.rng, names, allocator, context.day_number)
        if not roster.applicants:
            return

        # Take the best applicant the company can carry, judged on the skill it
        # most needs — an AI company staffs its weakest department first, which
        # is what keeps the research-approval-execution workflow of V8.3 able to
        # run end to end.
        wanted = self._weakest_department()
        affordable = [
            applicant for applicant in roster.applicants
            if cash > Money(applicant.salary.amount * months)
        ]
        if not affordable:
            return
        choice = max(affordable, key=lambda applicant: applicant.skills[wanted])
        hired, _ = roster.hire(choice, context.day_number)
        if hired:
            roster.assign_departments(choice, wanted, *self._other_departments(wanted),
                                      context.day_number)
            logger.debug("%s hired %s into %s.", self.company.name, choice.name, wanted)

    def random(self) -> float:
        """The next draw from this director's stream, for testing continuity."""
        return self.rng.random()

    def _weakest_department(self):
        from ..employees import Department

        return min(Department, key=lambda department: self.company.employees.output(department))

    def _other_departments(self, primary):
        from ..employees import Department

        rest = [department for department in Department if department is not primary]
        self.rng.shuffle(rest)
        return rest[0], rest[1]

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        """Including the random stream this director draws from.

        Its choices — which applicant, which departments — come out of that
        stream, and they reach the market as demand. If it restarted on every
        load, a reloaded world would diverge from the one that was saved
        (V15.11, V16.28).
        """
        return {
            "last_reviewed_day": self._last_reviewed_day,
            "rng_state": self.rng.getstate(),
        }

    def restore(self, data: dict) -> None:
        self._last_reviewed_day = data.get("last_reviewed_day")
        rng_state = data.get("rng_state")
        if rng_state is not None:
            # Tuples survive a round trip through most encodings as lists.
            version, internal, gauss = rng_state
            self.rng.setstate((version, tuple(internal), gauss))
