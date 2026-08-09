# Apex Horizon

**The official version of Apex Horizon** — a single-player business and
investment simulation game where you start as a small private investor and grow
into one of the world's largest financial empires.

> **Status: 0.1, playable.** Every system in the planned roadmap is built and
> covered by tests. Balance is still being tuned, and a few figures are
> deliberately left for the project manager to set — see
> [Known gaps](#known-gaps).

## Playing

```bash
uv sync                 # install dependencies
uv run python main.py   # play
```

The game opens on a Start Menu. Starting a game means choosing one of five save
slots and naming it; that slot is where the game lives from then on, autosaves
included. A new game begins with **$10,000 and no company**: you are an individual investor, and buying your first shares is how
you earn the $25,000 a company costs to found. Remaining an investor forever is
a legitimate way to play.

The simulation runs one in-game day per real second, adjustable to ×2 or ×3, and
pauses whenever a decision is open.

### The shape of a playthrough

    Individual investor  →  build personal wealth  →  unlock Create Company
                         →  found a company  →  hire, invest, grow
                         →  acquire companies  →  manage funds for others

## What is in the game

| System | What it does |
|---|---|
| **Market** | A living market of listed companies whose prices move on performance, industry, the economy, news, sentiment, supply and demand — never at random, and always explainable |
| **Economy** | Multi-year cycles of growth, slowdown, recession and recovery, with inflation and lending conditions that follow |
| **Portfolio** | Your own holdings, bought with your own money, kept entirely separate from any company's |
| **Company** | Found one, hire people, pay them, watch reputation and cash; it can go bankrupt, and you can start again |
| **Employees** | Individuals with skills, departments, hidden characteristics, training, pay and morale — they run the investment operation, you run them |
| **Investments** | Research finds an opportunity, management approves it, an investor executes it, and eventually sells it |
| **Unlock Tree** | 32 unlocks across seven branches; every one changes something |
| **News** | Generated from what actually happened, with bylines from the world's own press |
| **Analytics & Statistics** | Five reporting views, plus permanent lifetime records that survive bankruptcy |
| **AI companies** | Twelve rival investment firms playing by exactly the same rules, hiring, investing and acquiring |
| **Acquisitions** | Buy a company outright; it keeps operating in its own industry and pays its parent |
| **Investment Funds** | Manage capital for outside investors, whose confidence follows your record |
| **Saving** | Five slots; a game picks one when it is created and keeps it, autosaves included. Validated, repaired and migrated; a reloaded world continues identically |

## Design Bible

`docs/Apex Horizon 2.0 - Design Bible (Definitive Edition).pdf` is the source of
truth for all gameplay. By project-manager decision it is kept in `docs/`
locally but **not committed** (see `.gitignore`), so you will need your own copy
to work on the game.

Where the implementation departs from it, or where it was silent and a decision
had to be made, that is recorded in
[`docs/design-decisions.md`](docs/design-decisions.md) rather than left in the
code.

## Technical documentation

One document per major system, in [`docs/`](docs/README.md) — architecture, data
standards, the simulation clock, the world database, market, economy, company
and finances, employees, investments, news and analytics, acquisitions,
investment funds, AI companies, the save system, the interface, statistics and
tooling.

## Relationship to the legacy version

The original prototype lives on as a separate, preserved project:

> **Legacy version:** https://github.com/Trjo3012/Apex-Horizon-Legacy

The legacy build is complete and playable, and is kept for reference. This
repository is not a continuation of its codebase — it is a clean rebuild against
Design Bible 2.0. Ideas and lessons carry over; code does not.

## Development

The project uses [UV](https://docs.astral.sh/uv/) as its package and environment
manager, with Python and [pygame-ce](https://pyga.me/). Dependencies are kept
minimal by design and none may be added without approval.

```bash
uv sync --group dev                                              # dev tooling
uv run ruff check .                                              # lint
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -q     # 603 tests
```

Run all three before committing — they are exactly what CI runs.

### Developer console

Press **Ctrl+T** in the game, or type into the terminal that launched it — both
run the same commands:

```
> money player add 50000        # personal cash; 'money company' for the company
> time add 5year                # runs the real simulation, spread across frames
> unlock add create_company     # goes through the Unlock Tree and its effects
> unlocks                       # what is currently owned
> status                        # where the game currently stands
> help money                    # exact syntax, per topic
```

Commands act on the real game state, never on a debug-only copy. The console
executes nothing from the operating system, and nothing typed into it can crash
the game. The terminal half is inert when no terminal is attached, so it never
interferes with tests or CI.

### Balance

Every tunable value lives in [`config/gameplay.toml`](config/gameplay.toml), each
citing the Design Bible section it comes from, so balance can be changed without
touching simulation logic.

## Known gaps

- **Growth curve** — the target numbers for how fast a company should grow are a
  project-manager decision and have not been set.
- **Visual pass** — the Dashboard and a company's page have had the charts,
  meters and status indicators V14.3 asks for; the Market and Analytics screens
  have not yet had the same treatment.

## Continuous integration

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs lint and tests on
every push to `main`, on pull requests, and via manual dispatch.

## License

Apex Horizon is released under the [MIT License](LICENSE) —
© 2026 Trjo Development Studio. You're free to use, modify, and
redistribute it; just keep the copyright and license notice.
