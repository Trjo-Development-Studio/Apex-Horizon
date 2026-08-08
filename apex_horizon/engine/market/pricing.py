"""The share price model.

Design Bible V4.4 lists what moves a share price: company performance, economic
conditions, market sentiment, news, random market variation, and supply and
demand — and insists prices should never feel completely random, since every
movement must have a believable explanation. V4.21 goes further: movement must
always be traceable to an underlying cause, so that losses feel explainable
rather than punishing at random.

The model therefore computes each contribution separately and keeps the
breakdown, rather than collapsing everything into one opaque number. A day's
price change is the sum of:

* **Performance** — the company's own underlying business strength (V4.11).
* **Industry** — how this industry is faring relative to others (V4.12, V7.6).
* **Sentiment** — the prevailing bull or bear mood of the whole market (V4.5).
* **Supply and demand** — net buying or selling pressure, scaled by the size of
  the company, so the same order moves a small company more than a large one
  (V4.8).
* **Variation** — bounded random noise, the only part with no narrative cause.

The total is clamped so no combination can produce an implausible overnight
jump.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from random import Random

from ..config import Config, get_config
from ..values import Money, Percentage
from .listing import MarketListing, PriceChange

# Prices never reach zero through ordinary movement; a company leaves the market
# through delisting (V4.14) rather than by decaying to nothing.
MINIMUM_PRICE = Money("0.01")


@dataclass(frozen=True)
class PricingWeights:
    """How strongly each cause contributes to a day's price change."""

    performance: Decimal
    industry: Decimal
    sentiment: Decimal
    supply_demand: Decimal
    max_daily_change: Decimal

    @classmethod
    def from_config(cls, config: Config | None = None) -> PricingWeights:
        source = config or get_config()
        return cls(
            performance=Decimal(str(source.get_float("market.performance_weight"))),
            industry=Decimal(str(source.get_float("market.industry_weight"))),
            sentiment=Decimal(str(source.get_float("market.sentiment_weight"))),
            supply_demand=Decimal(str(source.get_float("market.supply_demand_weight"))),
            max_daily_change=Decimal(str(source.get_float("market.max_daily_change"))),
        )


def _clamp(value: Decimal, limit: Decimal) -> Decimal:
    return max(-limit, min(limit, value))


def compute_change(
    listing: MarketListing,
    *,
    industry_trend: float,
    sentiment: float,
    rng: Random,
    weights: PricingWeights,
    economy_influence: Decimal = Decimal(0),
) -> PriceChange:
    """Work out today's price change for one company, cause by cause.

    ``economy_influence`` is the contribution of economic conditions and
    inflation, supplied by the Economy System. V4.4 lists economic conditions as
    a distinct cause of price movement, so it is kept separate rather than
    folded into the industry or sentiment terms.
    """
    performance = Decimal(str(listing.performance)) * weights.performance
    industry = Decimal(str(industry_trend)) * weights.industry
    mood = Decimal(str(sentiment)) * weights.sentiment

    # Net demand as a fraction of shares in issue: the same order size moves a
    # small company far more than a large one (V4.8).
    if listing.shares_outstanding > 0 and listing.pending_demand:
        pressure = Decimal(listing.pending_demand) / Decimal(listing.shares_outstanding)
    else:
        pressure = Decimal(0)
    supply_demand = _clamp(pressure * weights.supply_demand, weights.max_daily_change)

    # Random variation, corrected so that noise alone does not move prices.
    #
    # Applying a symmetric random return multiplicatively every day is not
    # actually neutral: a 10% gain followed by a 10% loss leaves you below where
    # you started, so compounding drags the typical company steadily downward
    # even though each day's draw is even-handed. Over the hundreds of in-game
    # years a save may span that drag alone would bankrupt most of the market.
    # Adding half the variance cancels it, leaving randomness that genuinely
    # cuts both ways — which is what keeps a loss explainable by its cause
    # rather than by a hidden bias in the model (V4.21).
    sigma = float(listing.volatility.fraction)
    variation = Decimal(str(rng.gauss(0.0, sigma) + (sigma * sigma) / 2))

    total = _clamp(
        performance + industry + economy_influence + mood + supply_demand + variation,
        weights.max_daily_change,
    )
    return PriceChange(
        performance=Percentage(performance),
        industry=Percentage(industry),
        economy=Percentage(economy_influence),
        sentiment=Percentage(mood),
        supply_demand=Percentage(supply_demand),
        variation=Percentage(variation),
        total=Percentage(total),
    )


def apply_change(listing: MarketListing, change: PriceChange) -> Money:
    """Apply a computed change to a listing's price, returning the new price."""
    new_price = listing.price * change.total.scale_factor()
    if new_price < MINIMUM_PRICE:
        new_price = MINIMUM_PRICE
    listing.price = new_price
    listing.last_change = change
    return new_price
