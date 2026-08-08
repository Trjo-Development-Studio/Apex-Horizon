# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

This repository is the **official** version of Apex Horizon, a single-player
business and investment simulation game. It is a clean rebuild against **Design
Bible 2.0** — the design bible is the source of truth for features.

The original prototype is preserved separately as **Apex Horizon Legacy**
(`https://github.com/Trjo3012/Apex-Horizon-Legacy`). Code is not carried over
from it unless deliberately ported; ideas and lessons are.

**Current state: Milestone 0 (Foundation) complete** — layer structure, config,
logging, error handling, and the application shell. Gameplay systems are not yet
implemented; see `CHANGELOG.md` for progress and `docs/architecture.md` for the
technical design.

The project uses Python and Pygame (`pygame-ce`), with
[UV](https://docs.astral.sh/uv/) as its package and environment manager. Use
`uv run` / `uv add`; avoid `pip` unless instructed.

- Run: `uv run python main.py`
- Test: `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -q`
- Lint: `uv run ruff check .`

## Design Bible authority

`docs/Apex Horizon 2.0 - Design Bible (Definitive Edition).pdf` is the source of
truth for all gameplay design. It is kept locally but deliberately **not**
committed (see `.gitignore`). Key development rules it imposes (Volumes 15 & 19):

- **Never silently invent or change gameplay.** If a requirement is unclear,
  stop and ask — grouping multiple questions together (V19.4, V19.5).
- **Never add a dependency without approval** (V15.9, V19.15).
- **Test every completed feature**: build, launch, verify the feature, and
  confirm existing systems still work (V15.19, V19.12).
- **Update `CHANGELOG.md`** with every feature, improvement, refactor, and fix
  (V19.19, V19.21).
- **Configuration lives in `config/`**, never as literals in source (V15.10).
- **UI stays a presentation layer**; gameplay systems never import from `ui/`
  (V15.5).
- **Document major systems** in `docs/` as they are built (V15.14, V19.13).
- Development happens directly on `main`; feature branches are not used (V19.26).
- Version numbers are chosen by the project manager only (V19.29).

## Git workflow

This project uses Git for version control. The owner is new to Git, so Claude
manages it on their behalf.

**Batch related changes into fewer, larger commits — don't commit after every
small checkpoint.** Let changes accumulate and commit + push once the
uncommitted diff since the last commit exceeds ~150 changed lines (added +
deleted across all changes since the last commit, e.g. `git diff HEAD --numstat`
plus any new/untracked files), or when a logical unit of work is finished, or
when the owner asks. Always `git push` after committing so nothing is left
local-only — the batching is about *when* to commit, not whether to push.

Guidelines:
- Before committing, run the **same checks GitHub CI runs**
  (`.github/workflows/ci.yml`) and make sure they pass — a push must never fail
  the workflow:
  - `uv run ruff check .` (lint)
  - `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy uv run pytest -q` (tests)
  - confirm the game still launches (`uv run python main.py`). If any check
    fails, fix it and re-run before committing.
- Update `CHANGELOG.md` in the same commit as the work it describes (V19.21).
- After pushing, confirm the GitHub Actions run for the commit succeeds (the repo
  is public, so its status is queryable via the Actions API even without `gh`).
  If the workflow fails, fix the cause and push again until it is green.
- Stage with `git add` and commit with a clear, present-tense message describing
  what changed (e.g. "Add portfolio allocation chart").
- Keep commits focused: one logical change per commit when practical.
- The default branch is `main`, which tracks `origin/main` on GitHub
  (`https://github.com/Trjo3012/Apex-Horizon.git`). **Always `git push` after
  committing** so the remote stays up to date — never leave commits local-only.
- **Always verify each commit and push actually succeeded** (check the command
  result, e.g. it prints `main -> main` and `git status` shows the branch in
  sync). If a push or commit fails, say so plainly, then **retry or fix the repo
  to get it working and re-verify** — never assume it worked or stop at just
  reporting the failure. The same applies to any failing command (tests, build,
  launch): fix the underlying problem and confirm it passes.
- `.venv/`, caches, and build output are intentionally Git-ignored (see
  `.gitignore`) — don't commit runtime/generated files.
