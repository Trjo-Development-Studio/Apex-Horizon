# Changelog

All notable changes to Apex Horizon are recorded here, as required by Design
Bible V19.21. Entries cover features, improvements, refactors, bug fixes,
balance changes, and UI changes. Version numbers are set manually by the project
manager (V19.29).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
