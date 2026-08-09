"""The market system.

Design Bible Volume 4 defines a continuously simulated financial system that
operates independently of the player: companies rise and fall whether or not the
player invests, and the player is one participant inside a much larger world
(V4.2, V4.10). This module owns that simulation.

It runs during the Market phase of each day, which V29.10 places eighth —
share prices update after the day's investment activity has completed, so a
price reflects the full day rather than an incomplete subset of it.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal
from random import Random
from typing import TYPE_CHECKING

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import PeriodBoundary, SimulationContext, SimulationEngine, SimulationPhase
from ..values import Money, Percentage
from ..world import Industry, World, WorldGenerator
from .listing import MarketListing, PriceChange
from .pricing import PricingWeights, apply_change, compute_change

if TYPE_CHECKING:  # pragma: no cover - avoids a circular import at runtime
    from ..economy import EconomySystem
    from ..news import NewsSystem

logger = get_logger(__name__)


class MarketSystem:
    """Simulates share prices, industry conditions, and market sentiment."""

    def __init__(self, world: World, *, config: Config | None = None,
                 generator: WorldGenerator | None = None,
                 economy: EconomySystem | None = None,
                 news: NewsSystem | None = None):
        self.world = world
        self.config = config or get_config()
        self.weights = PricingWeights.from_config(self.config)
        self.generator = generator
        # Optional so the market can be simulated in isolation; when present,
        # economic conditions become a distinct cause of price movement (V4.6,
        # V4.4) and the market's mood follows the economy (V7.9).
        self.economy = economy
        #: Optional; when present, current stories push the prices they concern
        #: (V4.4, V10.10).
        self.news = news
        self.economy_weight = Decimal(str(self.config.get_float("economy.market_influence")))

        self.listings: dict[str, MarketListing] = {}
        # Per-industry conditions: different industries perform differently in
        # the same period (V4.5, V4.12).
        self.industry_trends: dict[Industry, float] = dict.fromkeys(Industry, 0.0)
        # Market-wide mood, negative in a bear market and positive in a bull
        # market (V4.5).
        self.sentiment: float = 0.0
        self._baseline_market_cap: Money | None = None
        # Guard so a retried simulation phase cannot move prices twice for one
        # day (see the retry-safety requirement in the simulation engine).
        self._last_priced_day: int | None = None

    # -- setup -----------------------------------------------------------
    def populate(self, rng: Random) -> None:
        """Create an opening listing for every company in the world."""
        low = self.config.get_int("market.starting_price_min")
        high = self.config.get_int("market.starting_price_max")
        shares_low = self.config.get_int("market.shares_outstanding_min")
        shares_high = self.config.get_int("market.shares_outstanding_max")
        vol_low = self.config.get_float("market.volatility_min")
        vol_high = self.config.get_float("market.volatility_max")
        history_days = self.config.get_int("market.price_history_days")

        for company in self.world.companies:
            listing = MarketListing(
                company_id=company.id,
                price=Money(str(round(rng.uniform(low, high), 2))),
                shares_outstanding=rng.randint(shares_low, shares_high),
                volatility=Percentage(str(round(rng.uniform(vol_low, vol_high), 4))),
                performance=rng.uniform(-0.5, 0.7),
                financial_health=rng.uniform(0.2, 0.9),
                reputation=rng.uniform(0.2, 0.9),
            )
            listing.history = deque(maxlen=history_days)
            listing.record_close()
            self.listings[company.id] = listing

        self._baseline_market_cap = self.total_market_cap()
        logger.info("Market opened with %d listings.", len(self.listings))

    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation. Prices update in the Market phase (V29.10)."""
        engine.register(SimulationPhase.MARKET, self.update_prices)
        engine.register_boundary(PeriodBoundary.WEEK, self.update_fundamentals)

    # -- daily simulation -------------------------------------------------
    def update_prices(self, context: SimulationContext) -> None:
        """Move every share price for one day (V4.4, V13.14)."""
        if self._last_priced_day == context.day_number:
            # A retried phase must not apply the same day's movement twice.
            return

        self._drift_sentiment(context.rng)
        for listing in self.listings.values():
            if listing.delisted:
                continue
            company = self.world.company_by_id(listing.company_id)
            trend = self.industry_trends.get(company.industry, 0.0) if company else 0.0
            change = compute_change(
                listing,
                industry_trend=trend,
                sentiment=self.sentiment,
                rng=context.rng,
                weights=self.weights,
                economy_influence=self._economy_influence(),
                news_influence=self._news_influence(listing.company_id),
            )
            apply_change(listing, change)
            listing.record_close()
            # Pressure is consumed by the price it produced (V4.8).
            listing.pending_demand = 0
            self._check_delisting(listing, context)

        self._last_priced_day = context.day_number

    def _economy_influence(self) -> Decimal:
        """Today's price contribution from economic conditions and inflation.

        V4.4 lists economic conditions as a distinct cause, and V7.5 makes
        inflation influence market valuations. Both are folded into one
        economic term rather than hidden inside the industry or sentiment
        contributions, so the player can be told which it was.
        """
        if self.economy is None:
            return Decimal(0)
        conditions = Decimal(str(self.economy.health)) * self.economy_weight
        return conditions + Decimal(str(self.economy.daily_inflation))

    def _news_influence(self, company_id: str) -> Decimal:
        """Today's price contribution from stories about this company (V10.10)."""
        if self.news is None:
            return Decimal(0)
        return Decimal(str(round(self.news.impact_for(company_id), 6)))

    def _drift_sentiment(self, rng: Random) -> None:
        """Move the market mood, pulling it toward the prevailing economy.

        Mean reversion keeps bull and bear markets as phases the market passes
        through rather than states it becomes stuck in (V4.5). When an economy
        is present the mood reverts toward economic health rather than plain
        neutrality, which is how the economy changes investment confidence
        (V7.9) without dictating prices directly.
        """
        drift = self.config.get_float("market.sentiment_drift")
        reversion = self.config.get_float("market.sentiment_reversion")
        # Sentiment leans toward the economy without simply mirroring it: the
        # economy already reaches prices directly through its own term, so a
        # full mirror would count the same conditions twice.
        anchor = self.economy.health * 0.5 if self.economy is not None else 0.0
        self.sentiment += rng.gauss(0.0, drift) - (self.sentiment - anchor) * reversion
        self.sentiment = max(-1.0, min(1.0, self.sentiment))

    # -- weekly fundamentals ---------------------------------------------
    def update_fundamentals(self, context: SimulationContext) -> None:
        """Evolve company performance and industry conditions (V4.11, V4.12).

        Underlying business performance changes gradually rather than daily, so
        a company's trajectory is something the player can recognise over time
        rather than noise.
        """
        performance_drift = self.config.get_float("market.performance_drift")
        industry_drift = self.config.get_float("market.industry_trend_drift")

        for industry in self.industry_trends:
            moved = self.industry_trends[industry] + context.rng.gauss(0.0, industry_drift)
            if self.economy is not None:
                # Industries are pulled toward how the economy treats them, so a
                # downturn hurts construction far more than healthcare (V7.6).
                target = self.economy.industry_relative_condition(industry)
                moved += (target - moved) * 0.15
                self.industry_trends[industry] = max(-1.0, min(1.0, moved))
            else:
                self.industry_trends[industry] = max(-1.0, min(1.0, moved * 0.95))

        for listing in self.listings.values():
            if listing.delisted:
                continue
            moved = listing.performance + context.rng.gauss(0.0, performance_drift)
            listing.performance = max(-1.0, min(1.0, moved))
            # Reputation and financial health follow performance slowly (V4.11).
            listing.financial_health = _towards(
                listing.financial_health, (listing.performance + 1) / 2, 0.05
            )
            listing.reputation = _towards(
                listing.reputation, (listing.performance + 1) / 2, 0.03
            )

        self._maybe_list_new_company(context)

    # -- long-term evolution (V4.14) --------------------------------------
    def _check_delisting(self, listing: MarketListing, context: SimulationContext) -> None:
        """Retire companies that have collapsed.

        V4.14 expects companies to become market leaders, stable businesses,
        declining organisations, or bankrupt ones over the years. A company
        trading below the floor for a sustained period leaves the market.
        """
        floor = Money(str(self.config.get_float("market.delisting_price_floor")))
        grace = self.config.get_int("market.delisting_grace_days")
        if listing.price < floor:
            listing.days_below_floor += 1
            if listing.days_below_floor >= grace:
                listing.delisted = True
                listing.delisted_on_day = context.day_number
                company = self.world.company_by_id(listing.company_id)
                logger.info(
                    "%s delisted after %d days below the price floor.",
                    company.name if company else listing.company_id,
                    grace,
                )
        else:
            listing.days_below_floor = 0

    def _maybe_list_new_company(self, context: SimulationContext) -> None:
        """Occasionally add a new listing so opportunities keep appearing (V4.14)."""
        if self.generator is None:
            return
        if len(self.active_listings()) >= self.config.get_int("market.max_listings"):
            return
        if context.rng.random() >= self.config.get_float("market.new_listing_weekly_chance"):
            return

        companies, leaders = self.generator.generate_companies(1, self.world.cities)
        self.world.companies.extend(companies)
        self.world.people.extend(leaders)
        for company in companies:
            self._add_listing(company.id, context.rng)
            logger.info("%s listed on the market.", company.name)

    def _add_listing(self, company_id: str, rng: Random) -> MarketListing:
        low = self.config.get_int("market.starting_price_min")
        high = self.config.get_int("market.starting_price_max")
        listing = MarketListing(
            company_id=company_id,
            price=Money(str(round(rng.uniform(low, high), 2))),
            shares_outstanding=rng.randint(
                self.config.get_int("market.shares_outstanding_min"),
                self.config.get_int("market.shares_outstanding_max"),
            ),
            volatility=Percentage(
                str(round(rng.uniform(
                    self.config.get_float("market.volatility_min"),
                    self.config.get_float("market.volatility_max"),
                ), 4))
            ),
            performance=rng.uniform(-0.3, 0.7),
        )
        listing.history = deque(maxlen=self.config.get_int("market.price_history_days"))
        listing.record_close()
        self.listings[company_id] = listing
        return listing

    # -- access (V4.15) ---------------------------------------------------
    def listing_for(self, company_id: str) -> MarketListing | None:
        return self.listings.get(company_id)

    def active_listings(self) -> list[MarketListing]:
        """Every company still trading."""
        return [listing for listing in self.listings.values() if not listing.delisted]

    def delist(self, company_id: str, *, reason: str = "") -> bool:
        """Take a company off the market permanently.

        Used when a company is acquired outright: its shares stop trading
        because there is nothing left to trade (project manager ruling, V12.5).
        Delisting is already how a company leaves the market (V4.14), so this
        reuses it rather than inventing a second way out.
        """
        listing = self.listings.get(company_id)
        if listing is None or listing.delisted:
            return False
        listing.delisted = True
        listing.delisted_on_day = self._last_priced_day
        listing.pending_demand = 0
        company = self.world.company_by_id(company_id)
        logger.info("%s delisted%s.", company.name if company else company_id,
                    f" ({reason})" if reason else "")
        return True

    def record_demand(self, company_id: str, shares: int) -> None:
        """Register buying or selling pressure from any market participant (V4.8).

        Used by the player's investors and by AI companies alike, so the market
        responds to the whole world's activity rather than the player's alone
        (V4.9, V4.10).
        """
        listing = self.listings.get(company_id)
        if listing and not listing.delisted:
            listing.add_demand(shares)

    def total_market_cap(self) -> Money:
        total = Money.zero()
        for listing in self.active_listings():
            total = total + listing.market_cap
        return total

    def market_index(self) -> float:
        """Total market value against its opening level, indexed to 1000."""
        if not self._baseline_market_cap or self._baseline_market_cap.is_zero:
            return 1000.0
        ratio = self.total_market_cap() / self._baseline_market_cap
        return float(ratio) * 1000.0

    def industry_performance(self, industry: Industry, days: int = 28) -> Percentage:
        """Average price change across an industry over recent trading."""
        listings = [
            listing
            for listing in self.active_listings()
            if (company := self.world.company_by_id(listing.company_id))
            and company.industry is industry
        ]
        if not listings:
            return Percentage.zero()
        changes = [listing.change_over(days) for listing in listings]
        known = [change.fraction for change in changes if change is not None]
        if not known:
            return Percentage.zero()
        # Averaged over the listings that actually have the history, so a
        # newly listed company does not drag the industry toward zero.
        return Percentage(sum(known, start=0) / len(known))

    def top_movers(self, count: int = 5) -> tuple[list[MarketListing], list[MarketListing]]:
        """The day's biggest gainers and losers, by actual price movement.

        Ranked on the change against yesterday's close, never on the size of the
        price itself and never at random. Ties are broken on company id so the
        same market always produces the same answer, rather than relying on
        whatever order the listings happen to be held in.
        """
        ranked = sorted(
            self.active_listings(),
            key=lambda listing: (listing.daily_change().fraction, listing.company_id),
        )
        return list(reversed(ranked[-count:])), ranked[:count]

    def top_gainer(self) -> MarketListing | None:
        """The day's best performer, or ``None`` if nothing actually gained.

        A market where everything fell has no top gainer. Reporting the least
        bad loser under that heading tells the player something untrue, so this
        says nothing instead and lets the interface word it.
        """
        gainers, _ = self.top_movers(1)
        if not gainers:
            return None
        best = gainers[0]
        return best if best.daily_change().is_positive else None

    def is_bull_market(self) -> bool:
        return self.sentiment > 0.2

    def is_bear_market(self) -> bool:
        return self.sentiment < -0.2

    def explain(self, company_id: str) -> str:
        """A short, believable explanation of a company's last movement (V4.4)."""
        listing = self.listings.get(company_id)
        company = self.world.company_by_id(company_id)
        if listing is None or company is None:
            return "No market data available."
        change = listing.last_change
        direction = "rose" if change.total.fraction > 0 else "fell"
        if change.total.is_zero:
            direction = "held steady"
        return (
            f"{company.name} {direction} {abs(change.total.as_percent):.2f}%, "
            f"driven mainly by {change.dominant_cause()}."
        )

    # -- persistence ------------------------------------------------------
    def state(self) -> dict:
        """Full market state for the save file.

        V4.22 requires market state, including every company's price history, to
        be saved in its entirety so that reloading never produces a different
        outcome than the player left.
        """
        return {
            "sentiment": self.sentiment,
            "industry_trends": {i.value: v for i, v in self.industry_trends.items()},
            "baseline_market_cap": str(self._baseline_market_cap.amount)
            if self._baseline_market_cap
            else None,
            "last_priced_day": self._last_priced_day,
            "listings": {
                listing.company_id: {
                    "price": str(listing.price.amount),
                    "shares_outstanding": listing.shares_outstanding,
                    "volatility": str(listing.volatility.fraction),
                    "performance": listing.performance,
                    "financial_health": listing.financial_health,
                    "reputation": listing.reputation,
                    "pending_demand": listing.pending_demand,
                    "delisted": listing.delisted,
                    "delisted_on_day": listing.delisted_on_day,
                    "days_below_floor": listing.days_below_floor,
                    "history": [str(price.amount) for price in listing.history],
                }
                for listing in self.listings.values()
            },
        }

    def restore(self, state: dict) -> None:
        """Restore market state saved by :meth:`state`."""
        self.sentiment = float(state.get("sentiment", 0.0))
        trends = state.get("industry_trends", {})
        for industry in self.industry_trends:
            self.industry_trends[industry] = float(trends.get(industry.value, 0.0))
        baseline = state.get("baseline_market_cap")
        self._baseline_market_cap = Money(baseline) if baseline else None
        self._last_priced_day = state.get("last_priced_day")

        history_days = self.config.get_int("market.price_history_days")
        self.listings = {}
        for company_id, data in state.get("listings", {}).items():
            listing = MarketListing(
                company_id=company_id,
                price=Money(data["price"]),
                shares_outstanding=int(data["shares_outstanding"]),
                volatility=Percentage(data["volatility"]),
                performance=float(data.get("performance", 0.0)),
                financial_health=float(data.get("financial_health", 0.5)),
                reputation=float(data.get("reputation", 0.5)),
                pending_demand=int(data.get("pending_demand", 0)),
                delisted=bool(data.get("delisted", False)),
                delisted_on_day=data.get("delisted_on_day"),
                days_below_floor=int(data.get("days_below_floor", 0)),
            )
            listing.history = deque(
                (Money(price) for price in data.get("history", [])), maxlen=history_days
            )
            listing.last_change = PriceChange()
            self.listings[company_id] = listing


def _towards(value: float, target: float, rate: float) -> float:
    """Move ``value`` a fraction of the way toward ``target``."""
    return max(0.0, min(1.0, value + (target - value) * rate))
