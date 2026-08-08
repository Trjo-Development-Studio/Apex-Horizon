# Design Decisions

The Design Bible is the source of truth for gameplay design (V19.3). Where it
deliberately leaves a value or behaviour undefined, the project manager decides
and the decision is recorded here, so no implementation choice is silently
invented (V19.5).

Entries marked **PM** are project-manager decisions. Entries marked
**Implementation** are choices made under V19.8 where the Design Bible defines a
standard but not its details; these are documented and open to revision.

## Money and progression

| Decision | Value | Bible gap |
|---|---|---|
| **PM** Company founding cost | **$25,000** personal cash | V3.3 |
| **PM** Starting personal capital | $10,000 — so the player must build capital before founding | V1.2 states $10,000 |
| **PM** Company bankruptcy threshold | Company cash reaches **−$1,000,000** | V3.20, V17.25 |
| **PM** Refounding requirement | At least **$500,000 personal net worth** | V3.3 |
| **PM** Employee capacity per company level | **10 / 25 / 50 / 100 / 200** for Levels 1–5 | V5.17, V18.5 |
| Personal bankruptcy threshold | −$250,000 (ends the playthrough) | Stated in V1.13 |

## Bankruptcy handling (PM, 2026-08-08)

The Design Bible flags several bankruptcy consequences as undefined (V3.20,
V5.23, V11.21, V12.21). The project manager's ruling, to be implemented in
Phase 7 and refined in Phases 15–16:

- **Subsidiaries** — a bankrupt parent loses ownership of them. Subsidiaries
  that can operate independently become independent companies; those that cannot
  are liquidated, according to their financial condition.
- **Investment funds** — funds are separate financial entities and do not
  automatically disappear with the company. Ownership and control pass through
  the bankruptcy process.
- **Employee training** — cancelled on bankruptcy. Employees return to their
  normal untrained state and may be hired elsewhere.
- **Scope** — keep bankruptcy reasonably simple for Apex Horizon 0.1 rather than
  building an elaborate insolvency simulation.

## Unlock Tree (PM, 2026-08-08)

The Design Bible defines the unlock structure and prerequisites (V6) but no
prices. Therefore:

- Unlock **costs and requirements must be data-driven and configurable** —
  never hard-coded into the unlock system.
- The unlock system is to be fully implemented and ready to accept final
  balancing values later, so the tree can be balanced without a rewrite.

## User interface (PM, 2026-08-08)

V14.4 cites `gantry.oljo.dev` as the sidebar reference, which is unavailable.
The sidebar icon style is therefore to be **clean, professional, simple,
recognisable, neutral/monochrome, and functional rather than decorative**,
consistent with the rest of the interface. No new visual style may be introduced
that conflicts with the Design Bible.

## Early-game pacing (PM, 2026-08-08)

The player begins with $10,000 (V1.2) and founding a company costs $25,000 (PM),
so the player must roughly triple their money before founding one. Measured
across six worlds, a diversified buy-and-hold position returned a median **6.1%
a year** — about **18 in-game years** to triple, and in one world the position
was still below its starting value after a decade.

V1.19's worked example describes a player founding a company after "several
in-game weeks", which the figures above do not support. The project manager was
shown the measurement and the alternatives, and ruled:

> **The long individual-investor phase is intended.** The founding cost stays at
> $25,000; the player trades personally for a long time before founding a
> company.

This is consistent with V1.20, which makes remaining an individual investor a
valid playstyle in its own right. The consequence for implementation is that the
opening of the game must stand on its own for many in-game years: personal
investing, the market, news and analytics all have to be worth using before a
company exists, and the route to a company has to read as a plan rather than a
locked door.

No personal income mechanic was added. The Design Bible describes none, and
inventing one would have been a new mechanic rather than an implementation
detail (V15.9, V19.4).

## Unlock pricing (PM, 2026-08-08)

Unlock prices must never be hard-coded. **Create Company is priced as a fraction
of the founding cost** rather than as a figure of its own, so the two stay in
proportion whenever either is retuned: `unlocks.create_company_cost_fraction`,
currently 0.2, giving $5,000 against a $25,000 founding cost.

## Content and assets

| Decision | Detail |
|---|---|
| **PM** Audio | Reuse the legacy prototype's cues for now; the Design Bible does not specify audio |
| **PM** Design Bible location | Kept in `docs/` locally, deliberately **not** committed |

## Implementation choices pending confirmation

These were made under V19.8 to keep development moving, and are flagged for the
project manager because each is a judgement call rather than a stated rule.

| Choice | Made | Why | Reversible? |
|---|---|---|---|
| **Calendar shape** — 4-week months, 12-month years (28-day months, 336-day years) | Phase 3 | V5.9 fixes seven-day weeks, but the Bible never states weeks per month. Uniform months let weeks nest cleanly inside months as the V13.6 display format implies | Yes — `config/gameplay.toml`, plus a save migration |
| **Price history retention** — 730 days of daily closes per company | Phase 5 | V4.22 wants history saved in its entirety, but V16.20 wants small saves across hundreds of in-game years; unbounded daily history is millions of points per save | Yes — configuration |
| **Sixteen industry naming identities** | Phase 4 | V32.7 requires every industry to have a documented naming philosophy but states only four | Yes — `industries.py` |
| **Industry economic sensitivity** | Phase 6 | V7.6 requires industries to respond differently to economic conditions but gives no values | Yes — configuration |
| **Day 1 is a Monday** | Phase 3 | The Bible references weekday names but never states a starting weekday | Yes |
