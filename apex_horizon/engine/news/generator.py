"""News generation.

Design Bible V10.2 has the News System continuously reporting what is happening
in companies, industries, the market and the economy — and V10.9 insists it
emerge from the simulation rather than being scripted. Every article here is
produced by looking at what the simulation actually did.

News runs in the News phase, which V29.3 places **first** in the day, and
deliberately reports on the *previous* day's settled outcomes. Processing it
first, from data that has already settled, is what guarantees an article always
describes something that has genuinely happened.

Tone follows V35.3: a Basic headline reads differently from a Breaking one even
when reporting a similar event, and headlines inform rather than predict
(V10.3).
"""

from __future__ import annotations

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..simulation import SimulationContext, SimulationEngine, SimulationPhase
from ..values import EntityKind, IdAllocator, Percentage
from .article import NewsArticle, NewsTier

logger = get_logger(__name__)

# Headline shapes. Kept as families rather than single strings so the same kind
# of event does not produce an identical article every time (V10.9).
COMPANY_RISE = (
    "{company} shares climb {change}",
    "{company} gains {change} as confidence builds",
    "Investors lift {company} by {change}",
)
COMPANY_FALL = (
    "{company} shares slide {change}",
    "{company} falls {change} amid weaker sentiment",
    "Selling pressure takes {company} down {change}",
)
BREAKING_RISE = (
    "{company} surges {change} in extraordinary session",
    "Breaking: {company} jumps {change}",
)
BREAKING_FALL = (
    "Breaking: {company} plunges {change}",
    "{company} collapses {change} in heavy trading",
)
INDUSTRY_STRONG = (
    "{industry} leads the market higher",
    "Strength across {industry} lifts the index",
)
INDUSTRY_WEAK = (
    "{industry} under pressure as the sector retreats",
    "{industry} lags a mixed market",
)


class NewsSystem:
    """Generates the world's news from what the simulation has done."""

    def __init__(self, world, market, economy, *, allocator: IdAllocator | None = None,
                 config: Config | None = None):
        self.config = config or get_config()
        self.world = world
        self.market = market
        self.economy = economy
        self.allocator = allocator or IdAllocator()
        self.articles: list[NewsArticle] = []
        #: Raised by the News branch of the Unlock Tree (V6.6.2, V10.4).
        self.tier: NewsTier = NewsTier.BASIC
        #: False until Basic News is unlocked: without it the player has no
        #: financial press at all, rather than a press showing nothing (V6.6.2).
        self.enabled: bool = True
        #: Live influence on prices, by company, decaying each day (V10.10).
        self.impacts: dict[str, float] = {}
        self._last_generated_day: int | None = None
        self._last_market_report_day: int = 0
        self._last_economic_state = getattr(economy, "state", None)
        #: Called with each new article, so the interface can surface it (V14.16).
        self.on_article: list = []

    # -- access ------------------------------------------------------------
    @property
    def available_tiers(self) -> list[NewsTier]:
        return [tier for tier in NewsTier if tier.value <= self.tier.value]

    def recent(self, count: int = 20, tier: NewsTier | None = None) -> list[NewsArticle]:
        """The archive, newest first (V10.15)."""
        articles = [a for a in reversed(self.articles) if tier is None or a.tier is tier]
        return articles[:count]

    def impact_for(self, company_id: str) -> float:
        """How strongly current news is pushing a company's price (V10.10)."""
        return self.impacts.get(company_id, 0.0)

    # -- simulation --------------------------------------------------------
    def register(self, engine: SimulationEngine) -> None:
        """Attach to the simulation (News is step 1 of the day, V29.3)."""
        engine.register(SimulationPhase.NEWS, self.generate)

    def generate(self, context: SimulationContext) -> None:
        """Report yesterday's settled outcomes (V29.3)."""
        if self._last_generated_day == context.day_number:
            return
        if not self.enabled:
            # Still mark the day, so unlocking the press later does not make it
            # suddenly report a backlog of events the player never lived through.
            self._last_generated_day = context.day_number
            return
        self._decay_impacts()
        self._report_companies(context)
        self._report_market(context)
        self._report_economy(context)
        del self.articles[: -self.config.get_int("news.archive_size")]
        self._last_generated_day = context.day_number

    def _decay_impacts(self) -> None:
        """News moves prices for a few days, not forever."""
        decay = self.config.get_float("news.impact_decay")
        self.impacts = {
            company_id: value * (1.0 - decay)
            for company_id, value in self.impacts.items()
            if abs(value * (1.0 - decay)) > 0.001
        }

    # -- company news (V10.5, V10.8) ---------------------------------------
    def _report_companies(self, context: SimulationContext) -> None:
        threshold = self.config.get_float("news.company_move_threshold")
        breaking = self.config.get_float("news.breaking_move_threshold")

        for listing in self.market.active_listings():
            change = listing.daily_change()
            size = abs(float(change.fraction))
            if size < threshold:
                continue
            company = self.world.company_by_id(listing.company_id)
            if company is None:
                continue

            is_breaking = size >= breaking
            if is_breaking and self.tier.value < NewsTier.BREAKING.value:
                # Without the Breaking News unlock the player simply does not
                # see the biggest stories (V10.16).
                continue
            rising = not change.is_negative
            if is_breaking:
                shapes = BREAKING_RISE if rising else BREAKING_FALL
                tier = NewsTier.BREAKING
            else:
                shapes = COMPANY_RISE if rising else COMPANY_FALL
                tier = NewsTier.BASIC

            shape = shapes[context.rng.randrange(len(shapes))]
            # The templates already say which way the price went, so the figure
            # is written without its sign: "slides 4.5%", never "slides -4.5%".
            magnitude = f"{abs(float(change.as_percent)):.1f}%"
            headline = shape.format(company=company.name, change=magnitude)
            cause = listing.last_change.dominant_cause()
            self._publish(
                context, tier, headline,
                f"{company.name} ({company.industry}) moved on {cause}.",
                company_id=company.id,
                impact=change,
            )

    # -- market news (V10.6) -----------------------------------------------
    def _report_market(self, context: SimulationContext) -> None:
        if self.tier.value < NewsTier.MARKET.value:
            return
        interval = self.config.get_int("news.market_report_interval")
        if context.day_number - self._last_market_report_day < interval:
            return
        self._last_market_report_day = context.day_number

        trends = self.market.industry_trends
        if not trends:
            return
        strongest = max(trends, key=lambda industry: trends[industry])
        weakest = min(trends, key=lambda industry: trends[industry])
        mood = (
            "a bull market" if self.market.is_bull_market()
            else "a bear market" if self.market.is_bear_market()
            else "steady conditions"
        )
        shape = INDUSTRY_STRONG[context.rng.randrange(len(INDUSTRY_STRONG))]
        self._publish(
            context, NewsTier.MARKET,
            shape.format(industry=strongest.value),
            f"The index stands at {self.market.market_index():,.0f} in {mood}. "
            f"{weakest.value} remains the weakest sector.",
        )

    # -- economic news (V10.7) ---------------------------------------------
    def _report_economy(self, context: SimulationContext) -> None:
        if self.tier.value < NewsTier.ECONOMIC.value or self.economy is None:
            return
        state = self.economy.state
        if state is self._last_economic_state:
            return
        previous, self._last_economic_state = self._last_economic_state, state
        self._publish(
            context, NewsTier.ECONOMIC,
            f"Economy moves from {previous} to {state}",
            f"Inflation stands at {self.economy.inflation.format()} a year. "
            "Banks are expected to adjust lending accordingly.",
        )

    # -- publishing --------------------------------------------------------
    def _publish(self, context: SimulationContext, tier: NewsTier, headline: str,
                 body: str, *, company_id: str | None = None,
                 impact: Percentage | None = None) -> NewsArticle:
        article = NewsArticle(
            id=self.allocator.next_id(EntityKind.NEWS),
            day=context.day_number,
            tier=tier,
            headline=headline,
            body=body,
            agency=self._agency_for(tier, context),
            company_id=company_id,
            impact=impact,
        )
        self.articles.append(article)
        if company_id and impact is not None:
            # A story pushes the price of the company it concerns, in the same
            # direction, for a few days (V10.10).
            strength = self.config.get_float("news.impact_strength")
            self.impacts[company_id] = (
                self.impacts.get(company_id, 0.0) + float(impact.fraction) * strength
            )
        for callback in list(self.on_article):
            callback(article)
        return article

    def _agency_for(self, tier: NewsTier, context: SimulationContext) -> str:
        """Give the story a byline from within the world (V33.10)."""
        agencies = self.world.news_agencies
        if not agencies:
            return ""
        financial = [a for a in agencies if a.specialises_in_finance]
        pool = financial if (financial and tier is not NewsTier.BASIC) else agencies
        return pool[context.rng.randrange(len(pool))].name

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "articles": [a.state() for a in self.articles],
            "tier": self.tier.name,
            "impacts": dict(self.impacts),
            "last_generated_day": self._last_generated_day,
            "last_market_report_day": self._last_market_report_day,
            "enabled": self.enabled,
        }

    def restore(self, data: dict) -> None:
        self.articles = [NewsArticle.from_state(a) for a in data.get("articles", [])]
        self.tier = NewsTier[data.get("tier", "BASIC")]
        self.impacts = {k: float(v) for k, v in data.get("impacts", {}).items()}
        self._last_generated_day = data.get("last_generated_day")
        self._last_market_report_day = int(data.get("last_market_report_day", 0))
        self.enabled = bool(data.get("enabled", True))
        self._last_economic_state = getattr(self.economy, "state", None)


