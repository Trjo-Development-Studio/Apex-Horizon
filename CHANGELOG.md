# Changelog

All notable changes to Apex Horizon are recorded here, as required by Design
Bible V19.21. Entries cover features, improvements, refactors, bug fixes,
balance changes, and UI changes. Version numbers are set manually by the project
manager (V19.29).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added — Milestone 11: News & Analytics (V10, V9)

The world now reports on itself, and the game reports back to the player. Code
lives in `apex_horizon/engine/news/` and `apex_horizon/engine/analytics/`, and is
documented in [`docs/news-and-analytics.md`](docs/news-and-analytics.md).

- **News generated from real events** (V10.9, V10.24): the News System runs
  first in the day (V29.3) over *yesterday's* settled data, so every headline
  describes something that genuinely happened. Company moves past 4.5% are
  reported, 12% is breaking, the market is surveyed weekly, and the economy is
  reported when it turns.
- **Bylines from the world** (V33.10): each story is attributed to one of the
  world's own news agencies, with financial specialists preferred for market and
  economic stories.
- **News moves prices** (V10.10): a story pushes the company it concerns for a
  few days, decaying as it ages. V4.4 lists news as a distinct cause of price
  movement, so `PriceChange` now carries a separate `news` term instead of
  folding it into sentiment — which is what lets the market name the news as the
  reason for a move (V4.21).
- **The archive, not a ticker** (V10.15): the last 120 stories stay readable on
  the News page, filterable by tier, with the selected story shown in full.
- **Tiered coverage** (V10.4, V10.16): Basic, Market, Economic and Breaking are
  raised through the Unlock Tree. A locked tier is genuinely withheld rather
  than shown in reduced detail.
- **Analytics across five views** (V9.5–V9.10): the company, its employees, the
  market, investments, and change over time — each gated by an analytics tier
  that adds depth rather than access. A report whose subject does not exist yet
  is absent rather than empty (V9.21).
- **Historical tracking** (V9.10): nothing else in the simulation remembered the
  past. A monthly snapshot of net worth, cash and the market index is now kept
  and charted, capped at `analytics.history_limit`.
- **Analysis stays out of the simulation** (V9.22): reports are plain data, and
  the page that draws them knows nothing about how any figure was reached.

### Fixed

- **Reloading a game could change its future** (V15.11, V16.28). The world
  generator's and name generator's random streams were not saved, so they
  restarted from the seed on every load — meaning a company listed after loading
  differed from the one an uninterrupted game would have listed. Both now carry
  their stream position in the save. Saves written before this change still
  load.
- Headlines reporting a fall read "down -4.5%", a double negative, because the
  template already supplied the direction. The figure is now written unsigned.

### Changed

- Only breaking news and shifts in the economy raise a notification. Every
  article did, which buried the screen in toasts and made the story that
  mattered no easier to notice than the rest (V10.14, V14.16).
- The sidebar gains an Analytics section, which V14.5 permits ("additional
  sections may be added as the game expands").

### Added — Milestone 10: Investment System (V8)

The company now earns. Code lives in `apex_horizon/engine/investments/` and is
documented in [`docs/investments.md`](docs/investments.md).

- **The full workflow** (V8.3): research discovers, management approves or
  rejects, an investor executes, the position is held, and the investor
  eventually sells. Each stage is independently timed, so a partly-completed
  workflow is a valid inspectable state (V8.24). It runs in the Employees phase
  so its demand reaches the market the same day (V29.10, V4.8).
- **Research is where skill pays** (V8.4, V9.5): a researcher compares several
  candidates and favours the one whose underlying business is performing. With
  skilled staff the companies chosen averaged +0.26 performance against a market
  average of −0.11, giving +6.4% per closed position at a 60% win rate — an
  edge, never a guarantee (V8.12).
- **Correct accounting**: buying is not an expense but an exchange of cash for
  an asset, so it never touches profit; selling books returned capital as
  financing and only the difference as profit or loss (V17.26, V9.12).
- **Limits and constraints** (V8.8, V8.22): per-investor limits, a position
  ceiling, and approved opportunities that wait rather than forcing a negative
  balance. Position size and sell targets come from hidden characteristics
  (V8.13).
- **Investments page**: open positions with unrealised gain, and the pipeline of
  what is awaiting review or execution.
- **25 further tests** (421 total).

### Fixed

- Salaries and running costs were wildly out of scale for a company founded with
  $25,000 — three employees cost more per year than the company would ever hold.
  Both are recalibrated so a first hire is affordable and payroll becomes a
  serious cost only as the organisation grows.
- Research had no predictive power, which meant buying with a target and a stop
  in a randomly moving market had no expected value: the company could never
  become profitable no matter how well it was run. Research now genuinely
  selects better-performing companies, in proportion to the researcher's skill.

### Added — Milestone 9: Employees & Company Management (V5, V18)

The company now has people. Code lives in `apex_horizon/engine/employees/` and
is documented in [`docs/employees.md`](docs/employees.md).

- **Three skills, three departments** (V5.4, V5.5): every employee has all three
  and is assigned a primary, secondary and third priority, performing best in
  their primary. One generalist can run an early company while specialisation
  still pays off later (V5.6).
- **Recruitment** (V5.3): candidates drawn from the same population as the rest
  of the world, with reputation shifting the distribution rather than
  guaranteeing quality. Skill ceilings follow the Better Employees tiers of
  V6.7.2.
- **Development and training** (V5.8, V5.9): experience accrues where work is
  done, so employees improve fastest in their primary department. Training is
  measured entirely in days and survives week and month boundaries.
- **Pay and morale** (V5.10, V5.11, V5.24): happiness follows pay measured
  against what an employee now believes they are worth. Because expectation
  derives from current skills, leaving a strong employee on their starting
  salary slowly costs performance rather than saving money for free.
- **Timeline** (V5.16): the previous ten in-game days per employee.
- **Capacity and bankruptcy**: capacity follows Company Level; on bankruptcy
  training is cancelled and staff released, wired through the company's
  bankruptcy callback so neither system knows the other's internals.
- **Interface** (V5.14, V5.15): Employee Management behind Company → Employees,
  with a searchable sortable list, and a details page carrying skills,
  department dropdowns, training, pay, timeline, and hidden characteristics
  gated until the Recruitment unlocks reveal them.
- **34 further tests** (396 total).

### Fixed

- Employee development was effectively invisible: at the original experience
  cost an employee gained nothing in a full in-game year, contradicting V5.8.
  Recalibrated to a little over one skill point a year in a primary department.
- Timeline markers used decorative glyphs that render as empty boxes in many
  system fonts — the same class of defect already fixed for sort markers.
  Markers are now plain ASCII.
- Repeated identical notifications now refresh rather than stacking, so routine
  messages such as autosaves cannot crowd out ones the player has not read
  (V27.7).

### Added — Milestone 8: Save System (V16)

Progress is now safe. Code lives in `apex_horizon/engine/save/` and is
documented in [`docs/save-system.md`](docs/save-system.md).

- **File format** (V16.18–V16.20): structured JSON, compressed, with a light
  obfuscation pass and a checksum. Small files that are not casually editable —
  explicitly not security, and not presented as such.
- **Atomic writes**: saves are written to a temporary file and moved into place,
  so an interruption mid-write cannot destroy the save that already existed.
- **Five manual slots plus one rolling autosave** (V16.7, V16.8), each an
  independent world, each carrying its own summary so a slot can be listed
  without loading it (V16.9). A slot that cannot be summarised is shown as
  damaged rather than hidden.
- **Validation, migration and repair** (V16.13–V16.15): an invalid save never
  silently loads. A damaged file has its contents salvaged where possible and
  the player is asked whether to try anyway; older formats migrate through a
  registry; repair is conservative and reports what it did.
- **Everything that affects gameplay is saved** (V16.11), including every
  listing's full price history (V4.22) and the generation state, so companies
  created after a reload never collide with earlier ones.
- **Autosaving** (V16.5, V16.6, V16.24): monthly by default, adjustable and
  switchable off, plus an autosave immediately before a major irreversible
  decision, with a brief non-pausing notification.
- **Save & Exit** (V16.3, V16.4): no standalone Save button; the workflow pauses,
  saves, and leaves only if that succeeds — a failed save returns the player to
  the running game rather than losing the session.
- **Export and import** (V16.21, V16.22), with an import refused before it can
  overwrite a slot if the file cannot be read.
- **World serialisation**: the world is generated from a seed but keeps growing
  during play, so its entities are saved rather than only the seed.
- **Slot management in Settings**, keeping the navigation V14.5 specifies
  unchanged.
- **46 further tests** (362 total), including a save, replay and reload that
  asserts every share price matches (V15.11, V16.28).

### Added — Milestone 7: User Interface framework (V14, V27)

The game is now visible and clickable. Code lives in `apex_horizon/ui/` and is
documented in [`docs/user-interface.md`](docs/user-interface.md).

- **Visual language** (V1.15, V14.3): a near-monochrome dark palette drawn from
  professional financial software, with colour reserved for meaning — one accent
  for the active element, green and red only for gain and loss. Everything
  visual comes from `theme.py`.
- **Icons** (V27.10): monochrome outline icons drawn rather than loaded, so the
  set stays one family and nothing can go missing at runtime. Every icon is
  paired with a label or tooltip.
- **Shared page layout** (V14.20, V14.28): header, breadcrumb, summary cards,
  search, content — positioned by the base `Page` class rather than by each
  page, so consistency is structural.
- **Sidebar and breadcrumbs** (V14.4-V14.6, V27.4): the eight sections V14.5
  names, and a clickable path so no page is ever a dead end.
- **Tables** (V14.8, V14.17, V27.2-V27.5): search that filters as you type,
  explicit sorting remembered per list, pagination, numeric columns aligned in a
  monospaced face, and a single click to open a row.
- **Popups** (V13.20, V14.15, V27.6): every popup pauses the simulation, offers
  a clear default and cancel, and only one decision is shown at a time.
- **Notifications** (V14.16, V27.7): lower-left, sliding in and out, never
  pausing the game, never stacking beyond what can be read.
- **Time controls** (V14.18, V27.9): ×1/×2/×3 always visible and reachable by
  keyboard, with no pause button — pausing happens only through popups.
- **Pages**: Dashboard, Company (with the founding flow), Market, a company
  drill-down showing *why* a price moved cause by cause, Financial Management,
  Settings, and honest empty states for the systems not yet built (V14.26).
- **29 further tests** (316 total), exercising real layout and rendering.

### Fixed

- Every "Today" column read 0.00%: the market appends today's close before
  anything reads it, so the daily change was comparing today with itself. Past
  prices were off by one day for the same reason.
- Right-aligned table headers collided with the next column, because headers
  used a different inset from their own cells.
- The sort marker rendered as an empty box — the arrow character is missing from
  many system fonts. Sort markers and pagination chevrons are now drawn rather
  than typed.

### Added — Milestone 6: Company & Financial Management (V3, V17)

The player can now found and run a company. Code lives in
`apex_horizon/engine/company/` and is documented in
[`docs/company-and-finances.md`](docs/company-and-finances.md).

- **Player and company as separate financial systems** (V1.4, V3.4): personal
  cash may move into the company and never back out. The rule is enforced
  structurally — `transfer_to_company` has no counterpart anywhere in the code.
- **Founding** (V2.4, V3.3): costs $25,000 against a $10,000 starting purse, so
  the player must build capital first. The cost becomes the company's opening
  capital by default, since a company founded with nothing could not act at all.
- **The append-only ledger** (V17.27): every movement of money records an entry,
  and the week, month, year, lifetime, per-category and cash-flow totals are all
  updated by that same call — consistent by construction rather than by
  discipline. Bounded for saves (V16.20) while lifetime totals persist.
- **Financial figures** (V17.6-V17.12): revenue, categorised expenses, profit,
  assets, liabilities, net worth, and company value with goodwill from sustained
  profit. Assets held by other systems arrive through registered providers, so
  each system keeps its own data (V15.7).
- **The company through time** (V13.9-V13.11): weekly operating costs and loan
  repayments, monthly closes, yearly profit tax. Reputation drifts toward
  sustained profitability in small steps, so trust is earned (V3.8).
- **Levels and capacity**: Company Level is raised by Unlock Tree purchases
  (V6.7.3), not automatically; capacity follows at 10/25/50/100/200.
- **Loans** (V17.13): terms come from the banks of V7.10, so borrowing already
  follows the economic cycle. Weekly repayments with interest on the declining
  balance.
- **Bankruptcy** (V3.14, V17.19): triggered at -$1,000,000 company cash, with
  other systems notified through callbacks so this module stays independent of
  employees, subsidiaries and funds. Company failure does not end the
  playthrough (V1.13); refounding requires $500,000 personal net worth.
- **42 further tests** (287 total).

### Fixed

- Owner capital and loan drawdowns were being counted as revenue, which inflated
  profit and would have let a player mistake borrowing for trading well —
  precisely the confusion V17.26 requires the interface to prevent. Financing is
  now a distinct kind of entry that moves cash and appears in cash flow but never
  touches profit. For the same reason, repaying loan principal is financing while
  only the interest is an expense.
- The refounding requirement was never applied to the first replacement company,
  because it tested a history that is only written once the replacement exists.

### Added — Milestone 5: Economy & Banking (V7, V25)

The economy now drives the world. Code lives in `apex_horizon/engine/economy/`
and is documented in [`docs/economy.md`](docs/economy.md).

- **Economic health** (V7.21): a single continuous value in [-1, +1] with the
  five states of V7.4 derived as thresholds over it, keeping the simulation
  deterministic while transitions stay gradual. Health and velocity behave as a
  damped oscillator whose period sets the length of a business cycle.
- **Five states** (V7.4): Growth, Stable, Slowdown, Recession, Recovery. Because
  health alone cannot separate a Slowdown from a Recovery, the state is derived
  from health *and* a smoothed trend, with hysteresis so a reported change always
  means something real.
- **Inflation** (V7.5, V25.2): moves toward a target set by conditions and
  accumulates into a price level, so nominal cash loses meaning over a long
  playthrough.
- **Industry response** (V7.6): every industry has a documented sensitivity —
  defensive industries barely notice the cycle, cyclical ones amplify it.
- **Banking** (V7.10, V25.3): interest rates, lending multiples, and trust
  requirements all follow the economy, so borrowing is cheap and generous in a
  boom and expensive and restrictive in a downturn — hardest exactly when it is
  most needed. Bank tiers make company reputation determine which banks are
  accessible (V33.4). Loans themselves belong to V17.13.
- **Market integration** (V4.4, V4.6, V7.9): economic conditions became a
  distinct, separately reported cause of price movement, industry trends follow
  the economy, and market sentiment leans toward economic health.
- **Project manager decisions recorded** in
  [`docs/design-decisions.md`](docs/design-decisions.md): company founding cost,
  employee capacity per level, bankruptcy thresholds and handling, unlock costs
  to remain data-driven, and the sidebar icon direction.
- **34 further tests** (245 total).

### Fixed

- The economic cycle was noise rather than a cycle: recessions arrived several
  times a year and lasted about three weeks. Because reversion acts on velocity,
  the cycle length is roughly 2*pi/sqrt(mean_reversion) days, so the constant had
  to fall by two orders of magnitude to produce the multi-year downturns V7.19
  describes.
- The state was named from a single day's movement, which reported a Slowdown
  roughly half the time even in a healthy economy; it now uses a smoothed trend.
- Recovery could never occur, because the two directional states were tested
  asymmetrically.
- Economic conditions reached share prices through three channels at once — the
  economy term, sentiment, and industry trends — compounding a sustained boom
  into a market index millions of times its opening level. Industries now
  contribute only their difference from the market average, and sentiment leans
  toward health rather than mirroring it.
- Capped share volatility, which compounds across the hundreds of in-game years
  a save may span and let the most volatile company dominate the index.

### Added — Milestone 4: Market System (V4)

The market now runs. Code lives in `apex_horizon/engine/market/` and is
documented in [`docs/market.md`](docs/market.md).

- **`MarketListing`** (V4.3): price, shares in issue, volatility, performance,
  reputation, financial health, and bounded price history. Market data lives
  here rather than on the company record, so each system owns its own state
  (V15.7) while the game still has only one company structure (V15.4).
- **Cause-by-cause price movement** (V4.4, V4.21): each day's change is the sum
  of company performance, industry conditions, market sentiment, supply and
  demand, and bounded random variation — and the breakdown is kept, so
  `market.explain()` can say *why* a price moved. The total is clamped so no
  combination can produce an implausible overnight jump.
- **Supply and demand** (V4.8): participants register buying or selling
  pressure, scaled by shares in issue so the same order moves a small company
  more than a large one. Pressure is consumed by the price it produces. The
  player's investors and AI companies will use the same entry point (V4.9).
- **Market-wide behaviour** (V4.5, V4.12): sentiment drifts daily with mean
  reversion so bull and bear markets are phases rather than permanent states;
  industry trends and company fundamentals evolve weekly so trajectories are
  recognisable rather than noise.
- **Long-term evolution** (V4.14): companies trading below the floor for a
  sustained period are delisted, and new companies list over time through the
  same world generator, so the market keeps producing fresh opportunities.
- **Statistics** (V4.15): market index, total capitalisation, top movers,
  industry performance, bull/bear state, and historical prices.
- **Determinism and saving** (V4.22, V15.11): every listing's full price history
  is saved, so reloading never produces a different outcome. `update_prices` is
  retry-safe and cannot move prices twice for one day (V15.26).
- **31 further tests** (211 total).

### Fixed

- Rebalanced the daily influence weights, which compounded to absurd growth —
  a 0.4% daily drift is roughly fourfold per year, and produced a
  five-thousand-fold market index across ten in-game years.
- Corrected random variation for compounding. Symmetric multiplicative returns
  are not neutral: a 10% gain followed by a 10% loss leaves you below where you
  started, which dragged the median company down about 70% per decade from
  noise alone. Adding half the variance cancels the drag.

### Added — Milestone 3: World Database & Generation (V32–V36)

The Alternative Earth now exists. Code lives in `apex_horizon/engine/world/` and
is documented in [`docs/world-database.md`](docs/world-database.md).

- **Curated word pools** (V32.2, V32.5): corporate word families including all
  thirteen the Design Bible names explicitly, invented-word fragments,
  internationally representative personal names, city components, and
  institutional vocabulary — all composed into names rather than stored whole,
  giving the "controlled variety" of V32.3.
- **Twenty industry naming identities** (V32.7): every industry in the Design
  Bible's list has a documented naming philosophy and its own nouns and
  patterns, so a player can often infer an industry from a company's name. Four
  identities come from the Design Bible directly; the other sixteen are
  documented here for the first time.
- **`NameGenerator`** (V33, V34.4): composes company, person, city, bank, news
  agency, university, organisation, and fund names, enforcing per-save
  uniqueness across three scopes so a world never contains a company and a bank
  sharing a name. Degrades to a plausible qualifier before ever repeating.
- **World entities** (V30.6): `Company` is the single company structure the
  whole game will use, as V15.4, V26.10 and V12.23 require — AI companies and
  subsidiaries reuse it rather than introducing parallel models.
- **`WorldGenerator`** (V34): builds one save's world — cities, companies with
  industries and named CEOs, banks, news agencies, universities, and regulators
  — dealing industries round-robin so all twenty are represented (V33.3).
  Generation state travels with the world so companies created later never
  collide with the originals.
- **Determinism** (V15.11, V34.6): the same seed regenerates an identical world;
  different seeds produce genuinely different ones (V34.2).
- **62 further tests** (180 total), including data-quality checks on the pools
  themselves and two rules found only by reading real generated output.

### Fixed

- Naming patterns no longer place the industry noun before its qualifier.
  Reversed forms such as "Foods Marigold" and "Masonry Onward" read as generated
  rather than chosen, failing V32.5's professional-tone rule.
- Partnership names no longer repeat a surname ("Gallagher & Gallagher
  Partners"); each placeholder occurrence is now filled independently.
- Removed a non-ASCII entry that had slipped into the invented-word fragments,
  which would have leaked unreadable characters into generated names.

### Added — Milestone 2: Time & Simulation Engine (V13, V29)

The simulation now runs. Code lives in `apex_horizon/engine/simulation/` and is
documented in [`docs/time-and-simulation.md`](docs/time-and-simulation.md).

- **`SimulationClock`** (V13.4, V13.5, V13.29): converts real elapsed time into
  whole in-game days at one second per day, scaled by ×1/×2/×3. Simulation pace
  is fully decoupled from frame rate — polling once a frame and once a second
  give identical results. Pausing banks no time, so unpausing never
  fast-forwards through a popup (V13.20); changing speed never disturbs banked
  time, so rapid switching cannot skip or duplicate ticks (V13.27); and days
  beyond the per-update cap are carried forward rather than dropped, keeping
  long unattended sessions deterministic.
- **`SimulationEngine`** (V15.4): owns in-game time, the seeded generator, and
  the system registry. Systems register phase handlers instead of calling one
  another, staying modular (V15.6, V15.7).
- **Ten ordered daily phases** (V29.2): News, Economy, Banks, Companies,
  Employees, Research, Investment Funds, Market, Financial Calculations, User
  Interface — each completing fully before the next, so no system ever reads
  partially-computed data (V29.13, V29.15). Registration order cannot affect
  execution order.
- **Scheduled progression** (V13.9–V13.11): weekly, monthly, and yearly handlers
  fire on the last day of each completed period, shortest first when several end
  together. Adds `is_last_day_of_week/month/year` to `SimulationDate`.
- **Background updates** (V13.19) roughly every five ticks, and **random event
  rolls** at the configured daily/weekly/monthly/yearly probabilities (V13.18).
  The engine decides only whether an event fires; content arrives with the
  Events database (V33.14).
- **Determinism** (V15.11): a single seeded generator drives every system, and
  saved state includes the generator's internal state so a reloaded world
  continues the same sequence rather than restarting it.
- **Error resilience** (V15.13, V15.26): every handler runs under the retry
  policy, so a failing system cannot end the game — later phases still run and
  time still advances. Handlers must therefore be retry-safe.
- **Shell integration**: the window now advances the simulation each frame and
  displays the live date, with 1/2/3 changing speed (V13.5, V27.9).
- **34 further tests** (119 total), including verification that a 3.5-second run
  advances exactly three in-game days.

### Added — Milestone 1: Data Standards (V30)

Shared value types in `apex_horizon/engine/values/`, enforced through types
rather than developer convention (V30.9), documented in
[`docs/data-standards.md`](docs/data-standards.md).

- **`Money`** (V30.2, V30.7): a single normalised internal currency wrapping
  `Decimal`, so `0.1 + 0.2` is exactly `0.3` and errors cannot compound across
  the hundreds of in-game years a save may span. Full precision is retained
  through every computation; rounding and the `$` symbol occur only at display.
  Money × Money and construction from `bool` both raise.
- **`Percentage`** (V30.3): stored as a fraction (5% is `0.05`, never `5`), with
  the `%` symbol applied only at display, plus `scale_factor()` for applying
  percentage changes.
- **`SimulationDate`** (V30.4, V13.6): in-game time as a single continuously
  incrementing day counter, from which the Year/Month/Week/Day calendar is
  derived — never the reverse. Immutable, with boundary helpers
  (`starts_new_week/month/year`) that will drive the scheduled events of
  V13.9–V13.11. The `Calendar` shape is configuration-driven.
- **`IdAllocator`** (V30.6): sequential per-kind identifiers such as
  `company-000001`, distinct from display names. Sequential rather than random
  so world generation is reproducible (V15.11); counters are saved with the
  world so identifiers never collide after a reload. `new_save_id()` provides
  the random Save ID required by V16.17.
- **Timestamps** (V30.5): ISO 8601 UTC helpers for save metadata, kept strictly
  separate from in-game time; naive datetimes are treated as UTC so an older
  save never fails to load over a missing offset.
- **55 further tests** (85 total), including a direct check of the Design
  Bible's own training example — a Friday plus ten days lands on a Monday.

Open interpretation, pending project manager confirmation: the Design Bible
states seven-day weeks but not weeks per month or months per year. Uniform
4-week months (28-day months, 336-day years) were chosen so weeks nest cleanly
inside months as the V13.6 display format implies. The values live in
`config/gameplay.toml`, so revising them is a configuration change.

### Added — Milestone 0: Foundation

- **Layer-based project structure** (V15.3): `apex_horizon/engine/` for
  simulation systems, `apex_horizon/ui/` for the presentation layer, plus
  top-level `config/`, `assets/`, `docs/`, and `tests/`.
- **Centralised gameplay configuration** (V15.10, V1.22): `config/gameplay.toml`
  holds every tunable value, each annotated with the Design Bible section it
  derives from. `apex_horizon/engine/config.py` provides typed, dotted-path
  access and fails loudly on missing or mistyped values.
- **Path resolution** (`engine/paths.py`): resolves bundled data (config,
  assets) and player-writable data (saves, logs) for both source runs and
  future PyInstaller builds.
- **Logging** (V15.12): rotating log file plus console output, capped at ~5 MB
  total. Logging failures degrade to console only rather than blocking play.
- **Error handling** (V15.13): `run_with_retry` implements the required policy —
  attempt, retry, retry again, then log the full traceback, notify the player,
  and ask them to report the issue. Failures return a result object instead of
  raising so gameplay can continue.
- **Application shell** (`ui/window.py`): a minimal window and frame loop so the
  mandatory "the game launches successfully" check (V15.19, V19.10) is
  verifiable from Milestone 0 onward. Placeholder pending the UI framework.
- **Test suite**: 30 tests covering configuration, logging, paths, the retry
  policy, and a headless launch test of the real window.
- **Tooling**: `pygame-ce` runtime dependency; explicit Ruff rule selection
  pinned in `pyproject.toml` so a future Ruff release cannot change the lint
  surface underneath CI (V19.11).

### Project manager decisions

Values the Design Bible deliberately left undefined, supplied by the project
manager on 2026-08-08 and recorded in `config/gameplay.toml`:

- Company bankruptcy occurs at **−$1,000,000** company cash (V3.20, V17.25).
- Founding a company costs **$25,000** of personal cash; the same figure gates
  re-founding after a bankruptcy (V3.3).
- Audio will reuse the legacy prototype's cues for now (the Design Bible does
  not specify audio).
- The Design Bible PDF lives in `docs/` locally and is deliberately not
  committed to the repository.
