# Employees & Company Management

Implements Design Bible Volumes 5 and 18. Code lives in
`apex_horizon/engine/employees/`.

Employees should feel like intelligent colleagues rather than automated income
generators (V5.26). Without individually distinct people, growing a company
would just be watching numbers rise (V5.19).

## Three skills, three departments (V5.4, V5.5, V18.6)

Every employee has **all three** skills — Research, Management, Investment — and
is assigned all three departments in a **priority order**: primary, secondary,
third. They perform best in their primary and least in their third.

That single rule is what lets one generalist run an early company (V5.6) while
specialisation still pays off later. Assigning departments swaps them rather
than duplicating, so all three always remain covered.

Effectiveness = skill ÷ ceiling × priority weight × morale, and is **zero while
training** — an employee cannot do their job and learn at the same time (V5.9).

## Recruitment (V5.3, V18.14)

Candidates are drawn from the same population as everyone else in the world
(V33.6), so a hire is a person from the Alternative Earth rather than a
generated string.

Reputation shifts the **distribution** rather than guaranteeing quality: a
well-regarded company sees better candidates on average, but a poor one can
still occasionally meet someone excellent. Skill ceilings follow the Better
Employees unlocks of V6.7.2 — 1–20, 1–30, 1–40, with a more modest pool before
any of them.

## Development and training (V5.8, V5.9, V13.12)

Experience accrues where work is actually done, so an employee improves fastest
in their primary department. Observed over five in-game years: primary 13 → 19,
secondary 13 → 16, third 10 → 11.

Training is measured **entirely in days** and continues across weeks and months —
beginning on a Friday for ten days finishes the following Monday, and changing
week never resets it.

## Pay and morale (V5.10, V5.11, V5.24)

Salary is derived from skill, so a strong hire is a commitment rather than a
free upgrade.

Happiness follows **pay measured against what the employee now believes they are
worth**, plus workload and company success. Because expectation is derived from
*current* skills, an employee who has grown since being hired expects more than
they are paid — so leaving a strong employee on their starting salary slowly
costs performance rather than saving money for free, which is exactly the
dynamic V5.24 describes. `Raise to market rate` closes the gap.

An unhappy employee still works, just less well: morale is a performance
multiplier, never a stoppage.

## Timeline (V5.16)

Each employee keeps a record of the previous ten in-game days — joining,
reassignment, training started and completed, skill improvements, pay changes.

Markers are restricted to **plain ASCII**: decorative glyphs are missing from
many system fonts and render as an empty box.

## Capacity and bankruptcy

Capacity comes from Company Level — 10 / 25 / 50 / 100 / 200 (project manager
decision). A company at capacity cannot hire even an excellent candidate, and
the interface says so plainly rather than failing confusingly (V18.29).

On bankruptcy, training is cancelled and everyone is released, free to be hired
elsewhere (project manager ruling). The roster attaches to the company's
bankruptcy callback, so neither system needs to know the other's internals.

## What employees do not do yet

What employees do with their working day — discovering, approving and executing
investments — is the Investment Workflow of Volume 8, and arrives next. This
milestone owns the people; the roster already exposes each department's daily
output (`research_output`, `management_output`, `investment_output`) for that
system to consume, and `can_operate` reflects V2.18: a company whose only
employee is training cannot run the loop at all.
