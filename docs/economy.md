# Economy & Banking

Implements Design Bible Volumes 7 and 25. Code lives in
`apex_horizon/engine/economy/`.

The economy runs whether or not the player acts (V7.3), cannot be controlled
(V7.2), and applies equally to every participant including AI companies (V7.13).
It updates in the Economy phase, which V29.4 places second in the day, so Banks,
Companies and the Market all read a freshly computed state.

## One continuous value, five named states

V7.21 specifies the model directly: a single continuous **health** value in
[−1, +1], with the five states of V7.4 derived as thresholds over it. That keeps
the simulation deterministic while letting transitions feel gradual.

Health alone cannot name all five states, though. A **Slowdown** and a
**Recovery** can sit at the same level — what separates them is *direction*.
The state is therefore derived from health **and** a smoothed trend:

| State | Condition |
|---|---|
| Economic Growth | health ≥ +0.35 |
| Recession | health ≤ −0.35 |
| Slowdown | trending down, from positive health |
| Recovery | trending up, from negative health |
| Stable Economy | otherwise |

Three details matter, each found by simulating decades and reading the output:

- **The trend must be smoothed.** Day to day the economy is as likely to tick
  down as up, so naming the state from one day's movement reports a Slowdown
  roughly half the time even in a healthy economy.
- **Slowdown and Recovery must be symmetric.** Testing direction alone for one
  but direction *and* side of the range for the other made Recovery literally
  never occur.
- **Hysteresis** widens the active state's threshold, so the economy must move
  meaningfully past a boundary before its name changes — otherwise a value
  hovering on a threshold flickers and a reported change stops meaning anything.

## Why the cycle is six years long

Because reversion pulls on *velocity* rather than on health directly, health and
velocity behave as a damped oscillator whose natural period is roughly
**2π/√(mean_reversion)** days. That single relationship sets the length of a
business cycle.

This is why `mean_reversion` is `0.00001` rather than something that looks more
reasonable: at that value the cycle runs about six in-game years, which is what
allows the *"extended Recession lasting several in-game years"* of V7.19. Values
a hundred times larger produce an economy that crosses in and out of recession
several times a year — noise, not a cycle.

Reversion pulls toward a mildly positive resting point, so expansions are
somewhat more common than contractions, as in a real economy.

Observed across many seeds and decades: **Growth ≈29%, Stable ≈33%,
Slowdown ≈11%, Recession ≈16%, Recovery ≈11%**, with recessions arriving roughly
once every fourteen years and lasting about two years on average, occasionally
as long as seven.

## Inflation (V7.5, V25.2)

Inflation moves toward a target set by economic conditions — hot in a boom,
cooling or negative in a downturn — and accumulates into a **price level** that
starts at 1.0. Over a long playthrough this is what makes nominal cash lose
meaning, as V25.2 intends. Typical: the price level roughly doubles over 30
in-game years.

## Industries respond differently (V7.6)

Every industry has a documented **sensitivity**: defensive industries below 1.0
(Healthcare 0.30, Pharmaceuticals 0.35, Food 0.40) supply things people buy
regardless of the cycle; cyclical industries above 1.0 (Construction 1.50,
Automotive 1.40, Mining 1.40) depend on discretionary and capital spending.
*The Design Bible requires the difference but gives no values, so these are
authored and configurable.*

Two figures are exposed, and the distinction matters:

- `industry_condition()` — **absolute**: how the industry is actually faring.
  This is what to report to the player.
- `industry_relative_condition()` — **relative to the market average**. This is
  what the market consumes.

The market applies economic conditions to every company once, through its own
economic term. If industry trends also tracked absolute health — and sentiment
mirrored it too — the same boom would be counted three times over and compound
into implausible growth. Industries therefore contribute only their *difference*
from the average, and sentiment only leans toward health rather than mirroring
it.

## Banking (V7.10, V25.3)

Banks update in the Banks phase (V29.5), third in the day, so their terms always
follow the state computed immediately before. Terms are **derived on demand**
rather than stored, so they can never drift out of step with the economy.

| Condition | Strong economy | Weak economy |
|---|---|---|
| Interest rate | Lower | Higher |
| Lending multiple | Higher | Lower |
| Trust requirement | Lower | Higher |

The trust requirement rising in a downturn is deliberate: refinancing becomes
hardest exactly when it is most needed, which is the pressure V7.19 describes.

Each bank has a **tier** (V33.4): higher-tier banks lend more cheaply but expect
more of a borrower, so company reputation (V3.8) meaningfully determines which
banks are accessible.

Loans themselves — taking one, repaying it, the interest accrued — belong to the
Financial Management System of V17.13 and arrive with that milestone. This
module governs only the conditions on offer.

## Determinism and saving

All randomness comes from the simulation's seeded generator. `state_data()`
saves health, velocity, trend, state, inflation, price level, and the recent
transition history (bounded, so saves cannot grow without limit). `update_daily`
is retry-safe and cannot advance the economy twice for one day (V15.26).
