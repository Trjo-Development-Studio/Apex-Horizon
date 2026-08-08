# Investment System

Implements Design Bible Volume 8. Code lives in
`apex_horizon/engine/investments/`.

This is the system that makes the company earn. V8.2 is explicit that the player
does not buy and sell personally: they build an organisation that researches,
evaluates, approves and executes, and their control is exercised upstream —
hiring, assignment, training and limits (V8.14).

## The workflow (V8.3)

```
Research discovers  →  Management reviews  →  Investor executes
                            ↓ rejects
                        discarded
                                          →  held  →  investor sells  →  profit or loss
```

Each stage is **independently timed** (V8.24), so an opportunity approved but not
yet executed is a valid, inspectable state rather than a transient detail. The
whole thing runs inside the Employees phase, fifth in the day, so the demand it
creates is already recorded when the Market prices at step eight (V29.10).

A company with no employees — or whose only employee is training — cannot
discover, approve or execute anything (V2.18).

## Where the returns actually come from

This is the heart of the system, and it took measurement to get right.

Buying with a target and a stop in a market that moves randomly has **no expected
value at all**. If research had no predictive power, no amount of good management
could ever make the company profitable, and the game would be unwinnable.

So research is where skill pays: a researcher compares several candidates and
favours the one whose *underlying business is genuinely performing*. A novice
weighs up two; a highly skilled one considers eight. Measured over three in-game
years with skilled staff, the companies chosen averaged a performance of **+0.26
against a market average of −0.11**, giving **+6.4% per closed position at a 60%
win rate**.

It remains an edge, not a guarantee — the strongest company can still fall
(V8.12), and research reduces uncertainty without removing it (V9.3).

## Money moves correctly

Buying is **not an expense**: it exchanges cash for an asset of the same value,
so it moves cash and shows in cash flow but never touches profit. Only the
eventual gain or loss does. Selling books the returned capital as financing and
the difference as profit or loss — so the player can see where company profit
genuinely came from (V9.12), and can never mistake deploying capital for losing
it. This is the same reasoning that keeps borrowing out of revenue (V17.26).

## Limits and constraints (V8.8, V8.22)

- Each investor has a limit the player sets (V5.13, V18.13); with none set they
  deploy a meaningful share of free cash but never all of it.
- An investor at their position ceiling declines further opportunities until one
  is sold.
- An approved opportunity the company cannot currently afford **waits** rather
  than forcing a negative balance.
- Position size and the sell targets come from the investor's hidden
  characteristics (V8.13): a cautious investor takes profits early, an
  aggressive one rides further.

## Balance — and what still needs your eye

Measured across several seeds, all values live in `config/gameplay.toml`:

| Company | Result |
|---|---|
| $25k, one entry-level hire, 8 years | roughly break-even (≈ $6k–$22k net worth) |
| $175k, three skilled hires, 6 years | grows, ≈ $150k–$449k net worth |

An entry-level company hovering near break-even is deliberate — progression has
to come from better people — but **the exact growth curve is a design decision
rather than an engineering one**. Salaries, running costs, the research edge and
position sizing are all configuration, so the shape of that curve can be tuned
without touching the workflow. *Flagged for the project manager.*

Getting here required correcting three things that only showed up by simulating
years and reading the numbers: salaries and running costs that were vastly out of
scale for a company founded with $25,000, and research that had no predictive
power at all.
