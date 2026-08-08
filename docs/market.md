# Market System

Implements Design Bible Volume 4. Code lives in `apex_horizon/engine/market/`.

The market is a continuously simulated financial system that operates
independently of the player (V4.2, V4.10). Companies rise and fall whether or
not the player invests; the player is one participant inside a much larger
world.

## Where market data lives

`Company` (in `engine/world/`) carries **identity** — who a company is.
`MarketListing` carries **market state** — price, shares in issue, volatility,
performance, reputation, financial health, and price history. Keeping them apart
means each system owns its own data (V15.7) while there is still only one
company structure in the game (V15.4).

## Price movement (V4.4, V4.21)

Prices update during the Market phase, which V29.10 places eighth in the day so
a price reflects the day's completed investment activity rather than part of it.

A day's change is the **sum of separately computed causes**, and the breakdown is
kept rather than discarded:

| Cause | Meaning |
|---|---|
| Performance | The company's own underlying business strength (V4.11) |
| Industry | How this industry is faring relative to others (V4.12) |
| Sentiment | The prevailing bull or bear mood (V4.5) |
| Supply & demand | Net buying or selling pressure, scaled by company size (V4.8) |
| Variation | Bounded random noise — the only part with no narrative cause |

This is what makes `market.explain(company_id)` possible:

> *"Horizon Geological fell 3.09%, driven mainly by ordinary variation."*

The total is clamped by `max_daily_change`, so no combination of causes can
produce an implausible overnight jump.

### Two balance rules that matter

Both were found by running a decade of simulation and reading the output, not by
the test suite — and both are now covered by tests.

**Weights compound daily.** A 0.4% daily drift is roughly a fourfold gain *per
year* and a five-thousand-fold gain per decade. The influence weights are
therefore deliberately tiny: `performance_weight = 0.0004` is about +14% a year
for the strongest possible company, which is the pace a genuinely strong company
should manage.

**Symmetric random returns are not neutral.** A 10% gain followed by a 10% loss
leaves you below where you started, so compounding drags the typical company
downward even though each day's draw is even-handed — enough to bankrupt most of
the market across hundreds of in-game years. Adding half the variance cancels
that drag, so randomness genuinely cuts both ways and a loss is explained by its
cause rather than by a hidden bias.

Observed result across several seeds over ten in-game years: the median company
lands within roughly ±10%, about half of companies are up and half down, the
spread runs from several hundred percent gains to near-total collapses, and the
index grows roughly two to three times.

## Supply and demand (V4.8)

Participants register pressure, which is consumed by the price it produces:

```python
market.record_demand(company_id, shares)   # positive buys, negative sells
```

Pressure is scaled by shares in issue, so the same order moves a small company
far more than a large one. The player's investors and AI companies use the same
entry point, so the market responds to the whole world's activity (V4.9, V4.10).

## Market-wide behaviour

- **Sentiment** drifts daily with mean reversion, so bull and bear markets are
  phases the market passes through rather than states it sticks in (V4.5).
- **Industry trends** drift weekly and independently, so industries diverge from
  one another in the same period (V4.5, V4.12).
- **Fundamentals** — performance, reputation, financial health — evolve weekly
  rather than daily, so a company's trajectory is something the player can
  recognise over time rather than noise (V4.11).

## Long-term evolution (V4.14)

- A company trading below the price floor for a sustained period is **delisted**;
  a brief dip does not qualify.
- **New companies list** over time, generated through the same world generator,
  so the market keeps producing fresh opportunities. A configured ceiling keeps
  the market from growing without bound.

## Statistics (V4.15)

`market_index()` (opening level 1000), `total_market_cap()`, `top_movers()`,
`industry_performance()`, `is_bull_market()` / `is_bear_market()`, and per-listing
history via `price_on()` and `change_over()`.

## Determinism and saving (V4.22, V15.11)

All randomness comes from the simulation's seeded generator, so the same seed
produces the same market. `state()` saves every listing's full price history
along with sentiment and industry trends, so reloading never produces a
different outcome than the player left.

Price history is bounded to `price_history_days` (default 730) so a save cannot
grow without limit across hundreds of in-game years (V16.20). Longer-term
summaries belong with Analytics. *Retention pending confirmation from the
project manager.*

`update_prices` is **retry-safe**: it records the last day it priced and returns
early if asked to repeat it, so a retried simulation phase (V15.26) cannot move
prices twice.
