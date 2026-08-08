# The Player, Personal Investing & Progression

Covers Design Bible **V1** (the player), **V3.3–3.4** (company creation, personal
vs company finances) and **Volume 6** (the Unlock Tree). It exists to record one
rule that touches nearly every system, and which is easy to get wrong in a way
that no single screen reveals:

> **The player and their company are two separate entities.**

Code lives in `apex_horizon/engine/portfolio/` and `apex_horizon/engine/unlocks/`,
with `Player` in `apex_horizon/engine/company/player.py`.

---

## The intended progression

    Start  →  Individual Investor  →  Build Personal Wealth
           →  Unlock Create Company  →  Pay $25,000  →  Found Company
           →  Build Company  →  Unlock further company systems

Each arrow is a real gate in the code, not a suggestion:

| Stage | Enforced by |
|---|---|
| Starts with $10,000 and no company | `player.starting_personal_cash`; `Player.company` is `None` |
| Can invest personally from day one | `Player.attach_market` gives every player a `PersonalPortfolio` |
| Create Company must be unlocked | `Player.can_found_company` checks `unlocks.has(CREATE_COMPANY)` |
| Unlocking ≠ founding | `UnlockTree.unlock` grants permission and nothing else |
| Founding costs $25,000 | `company.founding_cost`, charged in `Player.found_company` |
| One company at a time | `Player.can_found_company` refuses while one operates (V1.3) |

V1.20 makes the first stage a legitimate destination rather than a tutorial: a
player may choose never to found a company and remain an individual investor
indefinitely.

---

## Personal investing

`PersonalPortfolio` holds shares the player bought with their own cash.

* **It spends personal money only** (V1.4, V3.4). It has no access to company
  funds, and the company's own investment operation (Volume 8) is a separate
  system with separate holdings.
* **The player trades directly.** Where the company invests through employees —
  research finds, management approves, an investor executes (V8.3) — the player
  buys and sells themselves. That difference is what hiring people actually buys:
  leverage over the player's own time.
* **Orders reach the market** through `market.record_demand`, exactly as the
  company's do, so personal buying moves a price rather than drawing from an
  infinite pool (V4.8).
* **Cost basis is tracked per holding.** Selling part of a position releases
  cost in proportion, so the remainder still carries its own share of what was
  paid, and gains are measured against money actually spent.

Trading is done from a company's page in the Market; the Investments page leads
with the personal portfolio and shows the company's operation beneath it.

### Net worth

    personal net worth = personal cash + personal holdings + company value

The two pools stay separate while both counting toward the player's worth
(V1.6). Ownership is what links them: company money stays inside the company,
but its value belongs to the player.

---

## The Unlock Tree

Built as a directed acyclic graph with prerequisites as explicit edges, which is
what V6.19 asks for, so branches defined later attach without touching
traversal.

* **Basic Investing is owned from the start** (V6.4). It is what makes the
  opening playable.
* **Create Company** requires it, and costs `unlocks.create_company_cost`.
* Costs live in configuration, never in code, so the project manager can retune
  prices without a code change.

### Why only two nodes so far

V6.3 requires every unlock to provide a noticeable improvement or a new system.
Listing the whole tree now would put unlocks on sale that change nothing, so the
remaining branches — Analytics, News, Finance, Employees, Training, Recruitment,
Company, and finally Investment Funds — arrive with the systems they gate. The
page says so plainly rather than showing an empty roadmap.

---

## Correcting an earlier implementation

Before this was written the game founded companies from day one, had no personal
investing at all, and treated the company as the centre of the early game. The
first two stages of the progression above simply did not exist: a player who
started with $10,000 and needed $25,000 had no way to earn the difference.

The rule is easy to break one screen at a time, so it is worth restating: any
new system must ask whether it belongs to the **player** or to the **company**,
and must never assume a company exists.
