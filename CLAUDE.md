# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

This repository is the **official** version of Apex Horizon, a single-player
business and investment simulation game. It is a clean rebuild against **Design
Bible 2.0** — the design bible is the source of truth for features.

The original prototype is preserved separately as **Apex Horizon Legacy**
(`https://github.com/Trjo3012/Apex-Horizon-Legacy`). Code is not carried over
from it unless deliberately ported; ideas and lessons are.

**Current state: scaffolding only — no gameplay code yet.**

The project uses Python with [UV](https://docs.astral.sh/uv/) as its package and
environment manager. Use `uv run` / `uv add`; avoid `pip` unless instructed.

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
  - `uv run ruff check .` (lint, once Python code exists)
  - `uv run pytest -q` (tests, once a `tests/` suite exists)
  - sanity-check the app still launches. If any check fails, fix it and re-run
    before committing.
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
