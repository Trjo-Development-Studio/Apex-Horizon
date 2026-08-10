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

Unlock prices must never be hard-coded. **Prices are derived from the company
founding cost** rather than written individually, so everything stays in
proportion whenever any of it is retuned.

Each unlock declares how deep it sits in the tree and takes the matching
multiple from `unlocks.cost_multipliers`. Against a $25,000 founding cost that
runs from $5,000 at the branch roots to $1,000,000 at Company Analytics and
Investment Funds. Changing the founding cost rescales all 32 unlocks at once.

## Navigation and visual presentation (PM, 2026-08-08)

Two corrections, made after playing the build.

**The interface had become too application-like.** The project manager asked for
a presentation that reads as a management simulation rather than financial
software. Checking that against the Design Bible found a direct conflict: V1.15
calls for "the feeling of a professional desktop application", and V14.3 says
the style should "resemble modern business and financial software **rather than
a traditional video game**", naming professional financial platforms as a
primary inspiration.

> **Ruling: V1.15 and V14.3 stand.** The identity stays professional and
> restrained. What was actually wrong is narrower and real — V14.3 also names
> **business dashboards** as an inspiration, and the implementation had built
> tables where dashboards were asked for.

So the work is visualisation rather than restyling: charts, sparklines, meters,
status chips, richer cards and better density, with the palette and tone
unchanged. Note that V14.7 and V14.14 forbid graphs in default views and confine
them to pages the player explicitly opens, so charts appear on detail pages and
never on the Dashboard.

**There were too many top-level tabs.** Ten sidebar entries listed screens
rather than systems. The navigation is now one entry per major system:

    Dashboard | Market | Portfolio | Company | Unlocks | News | Settings

with **Save & Exit** as a separate action at the foot of the sidebar, since
leaving the game is not a destination (V16.4).

* **Portfolio** holds every holding the player has — Personal and Company behind
  a selector, plus Analytics and Statistics. The company view appears only once
  a company exists and never replaces the personal one, because the player
  invests personally long before they are a CEO (V1.19, V1.20).
* **Company** holds the business itself: overview, employees, financial
  management, subsidiaries and investment funds.
* **Dashboard stays** as its own entry, since V14.7 makes it the default view.

V14.5 lists Investments and Financial Management as sidebar sections, so folding
them into the systems they belong to departs from that list. Nothing became
unreachable — a test asserts every system V14.5 names can still be opened.

## Start Menu and navigation (PM, 2026-08-09)

The game opens on a Start Menu, and Save & Exit returns to it rather than
closing the program, which is what V16.4 describes. A failed save keeps the
player in the running game with the error, per V16.4 step 6, rather than
returning them to the menu — losing a session to a failed save would be the one
outcome V16.4 exists to prevent.

Settings moved out of the sidebar's main list to sit above Save & Exit at the
foot. The sidebar can be expanded to show names beside the icons by clicking the
wordmark; the state is remembered for the session.

**Top movers are measured over a period**, seven days by default
(`market.top_mover_period_days`). Measured over a single day the figure changed
about once a real second, since the simulation runs a day a second — correct,
but unreadable, and reported as feeling random. A week is long enough to mean
something and short enough to keep moving.

**Company order is fixed** by company id rather than by any changing figure, so
a company holds its position for the life of a save. Lists sort only when the
player asks (V27.3).

## Autosave frequency (PM, 2026-08-09)

**Autosaving is measured in real minutes, not in-game months** — every ten
minutes of play by default, adjustable in Settings and switchable off.

V16.5 says the game autosaves every in-game month. The Bible was written before
the clock had a speed: at one day a real second a month is twenty-eight seconds,
and nine at triple speed, so a player was getting a hundred-odd saves an hour.
The *intent* of V16.5 is unchanged — the player never loses much progress — but
the quantity that intent is about is the player's own time, which is what a real
interval measures. The rest of V16.5–V16.7 stands: still adjustable, still
switchable off, still one rolling autosave, still a save before every
irreversible decision (V16.6).

The counter only advances while the game is actually being played; time spent
on an open decision does not count, so a game left sitting on a popup will not
save itself repeatedly.

## The in-game console (PM, 2026-08-09)

The project manager specified an in-game developer console on **Ctrl+T** with
its own parser, running no operating-system commands. V15.18 asked for developer
commands *from the launching terminal*; both now exist and share one command
set, so neither can drift from the other. The specified syntax replaced the
terminal's older shorthand — `money 5000` became `money player add 5000` and
`days 30` became `time add 30day` — rather than two spellings being maintained.

Four judgement calls were made inside the brief, each because the specification
did not reach them:

**Time only moves forwards.** `time set` to a past date is refused. The engine
advances a day at a time and systems record as they go; there is no operation
that unlives a day, and reaching back by rewriting the counter would leave the
world in a state the simulation never produces. The command says so instead.

**Long jumps are spread across frames.** `time add 5year` is 1,680 days, which
takes roughly half a minute to simulate honestly. Run inside one command it
would freeze the window, which reads as a crash — so the command schedules the
days and the application advances a slice each frame
(`debug.fast_forward_budget_ms`), with the console counting them down.
`time cancel`, which the brief does not mention, exists so a jump entered by
mistake is not something to sit through.

**`unlock add` grants what the unlock requires, and `unlock remove` removes what
depended on it.** V6.9 makes progression strictly sequential, so a lone deep
unlock is not a state the game can otherwise reach. The brief asked for removal
to "handle it safely and report the issue rather than crashing", and this is the
safe handling: both report what they had to take with them.

**Company money moves through the company's books.** `money company add` arrives
as owner capital and `remove` leaves as financing, so the ledger and cash-flow
statement stay truthful. What the console skips is the price, which is its
purpose; faking the bookkeeping as well would make every financial page lie.

## Save slots and the Start Menu (PM, 2026-08-09)

**A save game belongs to one slot for its entire life**, chosen by the player
when the game is created: manual saves, autosaves, Save & Exit and loading all
use it.

This removes the separate rolling autosave of **V16.7**. The Bible put the
autosave in its own file alongside the five manual slots, which meant the Load
menu listed a sixth entry the player had never started, holding a world that was
usually a copy of one of the others. The intent of V16.7 — that autosaving never
accumulates files — is unchanged; it is achieved by replacing the game's own
save instead of a dedicated one. `autosave.ahsave` is no longer written, and a
leftover one from an older build is ignored rather than listed.

Nothing is stored to remember the binding: a game lives in the file it was
loaded from, so it survives restarting, loading, advancing time and closing the
program without any extra state that could disagree with the file on disk.

**New Game asks for a slot and a name before the world exists.** The slot list
shows every slot as empty or in use with what it holds, nothing is picked
automatically, and an occupied slot is confirmed before it is replaced.

Two consequences worth naming:

- **Saving into a different slot moves the game there.** The alternative is a
  game that keeps autosaving into a slot the player thinks they left behind.
- **A game built directly in code gets slot 1.** Only tests and tools do that;
  a player is always asked. Without it a directly built game would have no slot
  and would never autosave.

## The Start Menu background (PM, 2026-08-09)

The menu has a drawn backdrop rather than flat colour, so the first screen does
not read as an application that has not finished loading.

The first attempt was representational — a city skyline at dusk with an index
line rising over it. The project manager rejected it and chose **soft geometric**
instead: a dark base, subtle gradient and lighting variation, and faint
overlapping shapes and lines, with everything representational ruled out
(buildings, charts, axes, symbols, logos, real-world objects) along with large
high-contrast shapes and any visible grid, which is the shape that makes a
screen look like financial software.

It is drawn from the palette in `theme.py` and composed from constants written
in fractions of the window, so it is the same arrangement at every size and on
every launch with no randomness involved, and it costs one cached surface rather
than an asset. It is built as a reusable component so other full-screen menus
can use it later. V1.15's clean, modern, minimalistic identity is unchanged:
nothing in the backdrop rises above about a fifth of the brightness of the text
in front of it.

## The real logo (PM, 2026-08-09)

The project's actual logo — made outside the engine — replaces two of the
game's placeholder marks: the window icon (previously unset) and the sidebar's
"AH" text. The project manager chose these two specifically over a third option,
putting the logo on the Start Menu itself, which stays as it was.

Only a square crop of the mark is used, with the "Apex Horizon" wordmark
trimmed away: the wordmark reads at Start Menu size but not at a window icon or
a 30-pixel sidebar mark, where it would blur into the letterforms rather than
add to them. The source PNG (kept in the sibling Legacy project) has the full
lockup; the derived, monogram-only asset is what is committed here, since that
is the only size the official build currently uses.

This is the one deliberate exception to V1.15's "icons are drawn, not loaded"
rule (`docs/user-interface.md`): the project's real identity is not the kind of
mark a handful of simple shapes can stand in for.

## Deferred from the 2026-08-09 QA pass

An end-to-end pass across every page, save/load, and edge cases (bankruptcy,
capacity, an empty market, a long time-skip) turned up five findings. Three were
fixed the same day: bankrupt companies were still operable in the UI, the
notification stack could cover Hire buttons and other controls, and the
Analytics/Statistics pages carried dead standalone navigation keys that were
never registered as destinations. Two were deliberately left alone rather than
guessed at:

**Repeated positions in a fund's holdings.** The same company can appear
several times in one investment fund's position list. This has **not been
confirmed as a bug** — it may reflect genuinely separate purchases the fund
made at different times, which is a legitimate thing for a position list to
show, or it may be a case that should consolidate into one row. Nothing in the
investment/fund logic was changed on the strength of it merely looking
cluttered; that call needs a design decision, not a fix made without one
(V19.4: never silently change gameplay).

**Simulation cost possibly growing across simulated years.** Long automated
playthroughs were observed getting slower, but this was **not profiled**, so
the cause — and whether it is even real rather than an artifact of the specific
test run — is unknown. Before any optimisation, a dedicated profiling pass
needs to measure, separately: idle world simulation over a long period; one
active company over a long period; multiple active companies; the effect of
employee count; the effect of investment/fund position count; and whether cost
actually grows with simulated years, or is flat and something else in the test
made it look otherwise. Optimising any subsystem before that measurement exists
would be guessing at the cost of correctness risk for a problem that has not
been located, let alone confirmed.

## Subsidiaries as a progression gate (PM, 2026-08-10)

Subsidiaries — previously gated only by Company Level (V12.15) — now also
requires a new unlock, **Subsidiaries**, one leaf past Investment Funds on
the `FINAL` branch of the Unlock Tree. Buying moved from the Market page to
a dedicated Company → Subsidiaries → Buy flow at the same time.

This is a **progression-only** link, not a functional one: `SubsidiaryBook`
and `FundBook` remain completely independent at runtime — neither reads the
other, and V12.15's own growth-stage gate (company level) is unchanged. The
new unlock only adds an edge in the tree; it does not make Subsidiaries
depend on Funds functioning, and does not change how either system earns or
pays out. Existing saves are grandfathered: the unlock only gates *new*
acquisitions, so a company that already owned subsidiaries before this
shipped keeps them, and keeps earning from them, whether or not the new
unlock has been bought.

AI companies bypass this gate unconditionally, at population time and on
save load, the same way they already bypass the Unlock Tree for Employee
Training — they never purchase unlocks, so gating acquisitions behind one
without a bypass would have silently stopped every AI company in the game
from ever acquiring again (V12.14: AI organisations expand by acquisition
too).

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
