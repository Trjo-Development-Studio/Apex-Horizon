# Company & Financial Management

Implements Design Bible Volumes 3 and 17. Code lives in
`apex_horizon/engine/company/`.

The company is the heart of the game (V3.23): a persistent entity, separate from
the player, that every other system exists to strengthen.

## Two pools of money, one direction (V1.4, V3.4)

Personal money and company money are separate systems that must never merge.
The player may move personal cash **into** the company; the reverse is never
allowed.

That rule is enforced structurally: `Player.transfer_to_company` exists and has
no counterpart. There is no method anywhere that moves company money to the
player, so the rule cannot be broken by a caller making a mistake.

```python
player.transfer_to_company(Money(10_000), day)   # allowed
# there is deliberately no transfer_from_company
```

## Founding (V2.4, V3.3)

Founding costs **$25,000** (project manager decision) against a starting purse
of $10,000, so the player must build capital before founding their first
company — the deliberate open beginning described in V1.17.

By default the founding cost becomes the company's **opening capital** rather
than vanishing as a fee. A company founded with nothing could not act at all
until the player made a further transfer, which reads as a bug rather than a
decision. *Configurable, and pending project-manager confirmation.*

After a bankruptcy, refounding additionally requires **$500,000 personal net
worth**.

## Everything flows through one ledger (V17.27)

V17.27 requires every category of spending to write to a single append-only
ledger from which profit and the periodic reports are *derived* — never separate
running totals that could drift apart.

Every movement of company money therefore goes through `receive`, `spend`,
`receive_financing`, or `repay_financing`, each of which records an entry. The
week, month, year, lifetime, per-category and cash-flow totals are all updated
by that same single call, so they are consistent by construction rather than by
discipline.

A save cannot hold centuries of entries (V16.20), so the ledger keeps recent
entries in full, monthly summaries for history, and unbounded lifetime totals.

### Financing is not revenue

Money the company *receives* is not necessarily money it *earned*. Owner capital
and loan drawdowns move cash and appear in cash flow (V17.5), but they never
touch revenue, expenses, or profit.

This matters: V17.26 requires the interface to make it impossible for the player
to mistake strong top-line performance for genuine profitability. Counting a
loan as revenue would let borrowing look exactly like trading well. For the same
reason, repaying loan **principal** is financing, while only the **interest** is
an expense.

## What the company tracks

| Figure | Definition | Bible |
|---|---|---|
| Revenue | Money earned, before expenses | V17.6 |
| Expenses | Categorised: salaries, research, loan interest, investments, operational, acquisitions, tax | V17.7 |
| Profit | Revenue − Expenses, continuously and per period | V17.8 |
| Assets | Cash plus holdings reported by other systems | V17.9 |
| Liabilities | Outstanding loans | V17.10 |
| Net worth | Assets − Liabilities | V17.11 |
| Company value | Net worth plus a goodwill multiple of last year's profit | V17.12 |

Assets owned by other systems — investments, subsidiaries, funds — are supplied
through **registered providers** rather than duplicated here, so each system
keeps responsibility for its own data (V15.7):

```python
finances.register_asset_provider("investments", portfolio.total_value)
```

## The company through time

| When | What happens | Bible |
|---|---|---|
| Daily | Reputation drifts toward sustained profitability; bankruptcy is tested | V3.8, V29.6 |
| Weekly | Operating costs, loan repayments, weekly profit closes | V13.9 |
| Monthly | Month closes and is summarised; salaries will be paid here | V13.10 |
| Yearly | Profit tax charged, year closes | V13.11 |

Reputation moves in small steps toward a target set by whether the last month
was profitable, so a single good month never buys standing in the industry —
trust is earned (V3.8).

## Levels and capacity

Company Level is **not** raised automatically by growth: Levels 2–5 are unlocks
purchased in the Company branch of the Unlock Tree (V6.7.3). Capacity follows the
level — **10 / 25 / 50 / 100 / 200** employees (project manager decision, since
V5.17 and V18.5 tie capacity to level without giving numbers).

## Bankruptcy (V3.14, V17.19, V1.13)

A company goes bankrupt when its cash reaches **−$1,000,000**. Spending is
deliberately allowed to push cash negative: a company that cannot meet its
commitments is exactly what bankruptcy represents, and silently refusing
payments would make the consequence untraceable (V25.7).

Company bankruptcy does **not** end the playthrough (V1.13, V2.12) — only
personal finances reaching −$250,000 does.

Other systems react through registered callbacks, so this module never needs to
know about employees, subsidiaries, or funds:

```python
company.on_bankruptcy.append(my_system.release_everything)
```

Per the project manager's ruling (see `design-decisions.md`), on bankruptcy
employee training is cancelled and employees released, subsidiaries leave the
group to become independent or be liquidated according to their condition, and
investment funds — separate financial entities — do not simply vanish. Those
systems arrive in later milestones and attach here.

## Loans (V17.13)

Terms come from the banks of V7.10, so borrowing costs already follow the
economic cycle. Repayments fall due weekly (V13.9), with interest accruing on
the declining balance: each week the company repays a fixed share of principal
plus interest on what remains.
