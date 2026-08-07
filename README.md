# Apex Horizon

**The official version of Apex Horizon** — a single-player business and
investment simulation game where you start as a small private investor and grow
into one of the world's largest financial empires.

> **Status: in development.** This repository currently contains project
> scaffolding only — no gameplay code yet. The game is being rebuilt from the
> ground up against **Design Bible 2.0**.

## Relationship to the legacy version

The original prototype lives on as a separate, preserved project:

> **Legacy version:** https://github.com/Trjo3012/Apex-Horizon-Legacy

The legacy build is complete and playable, and is kept for reference. This
repository is not a continuation of its codebase — it is a clean rebuild. Ideas
and lessons carry over; code does not, unless deliberately ported.

## Planned scope

Apex Horizon is built around five pillars:

- **Investing** — buying and selling shares, building a diversified portfolio, dividends, market trends, risk.
- **Company Management** — founding and growing an investment company, hiring, salaries, efficiency, expansion.
- **Progression** — unlocking new systems over time through a research tree.
- **Analytics** — portfolio performance, company growth, charts, and historical data.
- **Expansion** — acquiring companies, subsidiaries, passive income, a global financial empire.

The game favours long-term progression and strategy over fast-paced play:
simple to learn, difficult to master.

## Development

The project uses [UV](https://docs.astral.sh/uv/) as its package and environment
manager.

```bash
uv sync --group dev     # install dev tooling (ruff, pytest)
uv run ruff check .     # lint
uv run pytest -q        # tests
```

Runtime dependencies are intentionally not pinned yet — they will be added once
Design Bible 2.0 settles the technical stack.

## Continuous integration

`.github/workflows/ci.yml` runs lint and tests on every push to `main`, on pull
requests, and via manual dispatch. The lint and test steps activate
automatically as soon as Python code and a `tests/` suite exist, so the scaffold
stays green in the meantime.

## License

Apex Horizon is released under the [MIT License](LICENSE) —
© 2026 Trjo Development Studio. You're free to use, modify, and
redistribute it; just keep the copyright and license notice.
