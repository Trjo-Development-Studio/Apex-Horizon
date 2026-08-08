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
* **Create Company** requires it, and is the first purchase of the game.
* Prices live in configuration, never in code. Each unlock declares how deep it
  sits and takes the matching multiple of `company.founding_cost` from
  `unlocks.cost_multipliers`, so retuning the founding cost rescales the whole
  tree at once.

### The whole tree

All 32 nodes of Volume 6 are present: the primary progression (V6.5), the
Analytics and News branches off Basic Investing (V6.6), the five Company Level 2
branches in the order V6.7 states, and Investment Funds where every branch
converges (V6.8). The contents live in `catalogue.py`, kept apart from the
machinery that reads them.

**What each branch does**, wired in `effects.py`:

| Branch | Effect |
|---|---|
| Analytics | Opens the Analytics page, then deepens it through four tiers (V9.6) |
| News | Opens the financial press, then the market, economy and breaking tiers (V10.4) |
| Finance | Opens borrowing, then improves the terms banks offer (V6.7.1) |
| Employees | Raises applicant skill ceilings to 20, 30 and 40 (V6.7.2) |
| Company | Company Levels 2–5, then Company Analytics (V6.7.3, V9.9) |
| Training | Opens training, then makes it teach faster (V6.7.4) |
| Recruitment | Reputation counts for more, a wider pool, then hidden strengths and performance become visible (V6.7.5) |

`UnlockEffects` is a *pusher*, not a set of hooks: systems never ask the tree
what the player owns, the tree configures them. That keeps every gameplay system
ignorant of progression (V15.7) — the market does not know the Unlock Tree
exists — and means the effects can be re-applied wholesale after loading, so a
restored game behaves exactly as the saved one did.

**Investment Funds is shown but cannot be bought.** V6.14 wants the remaining
tree visible as long-term ambition, while V6.3 forbids selling an unlock that
changes nothing; the node is drawn and marked "Coming later" until Volume 11
exists. Any unlock can be held back this way with `implemented=False`.

### Two roots with no effect of their own

**Create Company** acts on the founding gate in `Player`, not on any system the
effects layer configures. **Employees** is purely structural, opening the quality
levels beneath it — a project-manager ruling, taken so that hiring stays
available from founding as V1.19's example shows. A test asserts every *other*
purchasable unlock measurably changes the game (V6.3), with these two named as
the exceptions.

---

## Correcting an earlier implementation

Before this was written the game founded companies from day one, had no personal
investing at all, and treated the company as the centre of the early game. The
first two stages of the progression above simply did not exist: a player who
started with $10,000 and needed $25,000 had no way to earn the difference.

The rule is easy to break one screen at a time, so it is worth restating: any
new system must ask whether it belongs to the **player** or to the **company**,
and must never assume a company exists.
