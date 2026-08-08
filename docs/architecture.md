# Architecture

Implements Design Bible Volume 15 (Technical Architecture). This document
describes what exists today and the shape the rest of the game is being built
into. It is updated as each milestone lands.

## Layer structure (V15.3)

The project is organised by technical layer, not by gameplay system. Gameplay
systems live *inside* the engine with a clean internal structure; they do not
each receive a top-level folder.

```
apex_horizon/
  engine/      Simulation, configuration, logging, error handling
  ui/          Presentation layer only — no business logic (V15.5)
config/        Gameplay configuration files (V15.10)
assets/        Bundled images and sounds
docs/          Technical documentation (V15.14) and the Design Bible
tests/         Automated tests (V15.19, V19.12)
main.py        Entry point
```

## Engine foundations (implemented)

### Configuration — `engine/config.py`

All tunable gameplay values live in `config/gameplay.toml`, never as literals in
source (V15.10). Values are read through typed accessors using dotted paths:

```python
from apex_horizon.engine import get_config

cash = get_config().get_int("player.starting_personal_cash")
```

A missing key raises `ConfigError` rather than defaulting silently, so a
configuration mistake surfaces immediately instead of propagating a zero deep
into the simulation. Each entry in the TOML file cites the Design Bible section
it comes from, and project-manager decisions are marked as such.

### Paths — `engine/paths.py`

Separates **bundled** read-only data (config, assets) from **player-writable**
data (saves, logs). Running from source keeps both inside the project; a frozen
PyInstaller build reads bundled data from the extraction directory and writes
player data to the platform's standard user data location.

### Logging — `engine/logging_setup.py`

A rotating file handler (~5 MB total) plus console output, covering errors,
warnings, simulation events, and debug information (V15.12). If the log
directory cannot be created the game continues with console logging only —
losing logs never prevents play.

### Error handling — `engine/errors.py`

`run_with_retry` implements V15.13 exactly: attempt, retry, retry again, and on
final failure log the complete traceback, notify the player, and ask them to
report the issue. It returns an `OperationResult` instead of raising, so callers
can continue gameplay after a recoverable failure.

Player notification uses a subscriber callback list rather than importing UI
code, keeping game logic independent of the interface (V15.5):

```python
subscribe_error_notifier(my_display_function)
```

`log_simulation_event` is the single entry point for recording significant
simulation events. The News System and Employee Timelines are expected to read
from this same history later (V10.24).

## Planned architecture

### Simulation engine (V15.4, V29)

A central engine will coordinate modular systems, executing ten ordered phases
per in-game day, each completing fully before the next begins so that no system
ever reads partially-computed data (V29.13, V29.15):

1. News · 2. Economy · 3. Banks · 4. Companies · 5. Employees · 6. Research ·
7. Investment Funds · 8. Market · 9. Financial Calculations · 10. User Interface

### Determinism (V15.11)

Loading a save must restore an identical simulation state. Simulation tick
processing will be decoupled from render frame rate (V13.29), and all randomness
will be seeded per save so a reloaded world never diverges.

### Data standards (V30)

Shared internal types — a single money type, percentage type, and simulation
date type — will be enforced through code rather than convention. Time is
tracked as one continuously incrementing day counter, from which the
Year/Month/Week/Day calendar is *derived*, never the reverse (V30.4). Financial
maths retains full precision, rounding only at display (V30.7).

## Conventions

- **UI separation** (V15.5): gameplay systems never import from `ui/`.
- **Modularity** (V15.7): changes to one system should not ripple into unrelated
  ones; shared behaviour is reused through composition rather than duplication.
- **Performance** (V15.8): clean architecture and readability come first;
  optimise only when a real problem exists.
- **Dependencies** (V15.9, V19.15): kept minimal; new ones require approval.
