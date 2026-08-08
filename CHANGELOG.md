# Changelog

All notable changes to Apex Horizon are recorded here, as required by Design
Bible V19.21. Entries cover features, improvements, refactors, bug fixes,
balance changes, and UI changes. Version numbers are set manually by the project
manager (V19.29).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
