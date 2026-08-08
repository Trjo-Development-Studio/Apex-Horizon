# Investment Funds

Covers Design Bible **Volume 11**. Code lives in `apex_horizon/engine/funds/`,
with the pages in `apex_horizon/ui/pages/funds.py`.

Funds are the last system the player unlocks, and the one that changes what the
company *is*: from a business investing its own wealth to one trusted with other
people's (V11.15, V11.24).

---

## Whose money it is

V11.5 is the rule everything else follows from:

> The money inside a fund belongs to the fund's investors, not the player
> personally. The company earns income by successfully managing these
> investments.

So a fund holds its own `CompanyFinances`, entirely separate from the company's,
and **assets under management are deliberately not registered as a company
asset**. Managing money is not owning it. What the company owns is the fee it
has already earned — the only money that ever crosses from a fund to the company.

Investor capital arriving in a fund is recorded as financing rather than
revenue, for the same reason an owner's capital is in a company: the fund was
entrusted with it, it did not earn it (V17.26).

---

## Composition, not duplication

V11.23 asks for funds to share the Volume 8 investment workflow through
composition so that a fix to that workflow applies to both. The workflow only
ever asks its owner for three things:

* `bankrupt`
* `employees`
* `finances`

A fund supplies exactly those — its own finances, the company's employees
(V11.14), and never bankrupt — and then runs the identical
research → approval → execution → sale process (V11.9). There is no
fund-specific investing code at all. Only the source of capital changes.

This is the third system built this way, after AI companies (V26.10) and
subsidiaries (V12.23). The Design Bible asks for it each time, and each time it
means the new system inherits every past and future fix for free.

---

## Confidence and growth

V11.11 has external investors judging the company's long-term record, and V11.20
makes the consequence explicit: deposits grow **without any direct action from
the player**. That is the point of the system — the player's job is to manage
well, and capital follows the record.

* Confidence runs 0 to 1 and moves slowly toward what the fund's total return
  justifies, so trust is earned and lost over time rather than in a month.
* Above `funds.deposit_confidence_threshold`, investors add money each month in
  proportion to what the fund already manages, scaled by their confidence.
* A fund that loses money sees confidence fall and future funding shrink.

Measured over five in-game years, a fund seeded with $250,000 grew to $916,000
with confidence rising from 50% to 89%, paying the company $51,645 in fees.

---

## What is deliberately not handled

V11.21 states that what happens to a fund that becomes **deeply insolvent** is
not yet defined and should be clarified in a future volume. Nothing is invented
here: confidence collapses and funding shrinks, and that is all. A fund is never
bankrupt in its own right.

An empty fund with no investments yet is a valid state, not an error — V11.21
says so explicitly, and the page says so too rather than looking broken.
