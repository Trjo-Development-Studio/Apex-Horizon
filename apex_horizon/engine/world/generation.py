"""World generation.

Design Bible Volume 34 defines how the curated databases of Volume 33 are
assembled into one specific save world. Generation happens exactly once, at save
creation; from that moment the Deterministic Simulation guarantee of V15.11
takes over and the generated world must remain identical across every later load
(V34.6).

Two principles shape this module:

- **Every save should feel unique** (V34.2). The databases are treated as a
  large shared pool from which each save draws its own combination, rather than
  a fixed roster replayed identically in every playthrough.
- **Curated selection over pure randomness** (V34.4). Names come from the
  curated pools and industry patterns of V32, never from unconstrained
  generation, so a generated world still feels handcrafted (V32.4).
"""

from __future__ import annotations

from random import Random

from ..config import Config, get_config
from ..logging_setup import get_logger
from ..values import EntityKind, IdAllocator
from .entities import (
    Bank,
    City,
    Company,
    NewsAgency,
    Organisation,
    Person,
    University,
    World,
)
from .industries import ALL_INDUSTRIES, Industry
from .names import NameGenerator

logger = get_logger(__name__)


class WorldGenerator:
    """Builds one save's world from the curated databases."""

    def __init__(
        self,
        rng: Random,
        *,
        allocator: IdAllocator | None = None,
        names: NameGenerator | None = None,
        config: Config | None = None,
    ):
        self.rng = rng
        self.allocator = allocator or IdAllocator()
        self.names = names or NameGenerator(rng)
        self.config = config or get_config()

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        """The generator's own random state (V15.11).

        The generator keeps producing companies long after the world is first
        built — the market lists a new one every so often (V4.13). If its random
        stream restarted from the seed on every load, a company founded after
        loading would come out different from the one an uninterrupted game
        would have founded, so a save would quietly change the future. Carrying
        the stream position in the save is what stops that.
        """
        return {"rng_state": self.rng.getstate()}

    def restore(self, data: dict) -> None:
        rng_state = data.get("rng_state")
        if rng_state is not None:
            # Tuples survive a round trip through most encodings as lists.
            version, internal, gauss = rng_state
            self.rng.setstate((version, tuple(internal), gauss))

    # -- industry distribution -------------------------------------------
    def _industry_plan(self, count: int) -> list[Industry]:
        """Spread companies across every industry rather than clustering them.

        V33.3 requires companies to be distributed across every industry listed
        in V32.7 rather than concentrated in a small subset. Dealing industries
        round-robin guarantees even coverage; shuffling the order keeps which
        industries receive the remainder different between saves (V34.5).
        """
        industries = list(ALL_INDUSTRIES)
        self.rng.shuffle(industries)
        plan = [industries[index % len(industries)] for index in range(count)]
        self.rng.shuffle(plan)
        return plan

    # -- individual categories -------------------------------------------
    def generate_cities(self, count: int) -> list[City]:
        return [
            City(id=self.allocator.next_id(EntityKind.CITY), name=self.names.city_name())
            for _ in range(count)
        ]

    def generate_person(self) -> Person:
        return Person(
            id=self.allocator.next_id(EntityKind.CEO),
            name=self.names.person_name(),
        )

    def generate_companies(self, count: int, cities: list[City]) -> tuple[list[Company], list[Person]]:
        """Create companies, each with an industry, a home city and a named CEO.

        V33.5 expects the CEO population to be roughly proportional to the
        company database, since most companies should have a named leader.
        """
        companies: list[Company] = []
        leaders: list[Person] = []
        for industry in self._industry_plan(count):
            ceo = self.generate_person()
            leaders.append(ceo)
            companies.append(
                Company(
                    id=self.allocator.next_id(EntityKind.COMPANY),
                    name=self.names.company_name(industry),
                    industry=industry,
                    headquarters_id=self.rng.choice(cities).id if cities else None,
                    ceo_id=ceo.id,
                )
            )
        return companies, leaders

    def generate_banks(self, count: int, cities: list[City]) -> list[Bank]:
        return [
            Bank(
                id=self.allocator.next_id(EntityKind.BANK),
                name=self.names.bank_name(),
                headquarters_id=self.rng.choice(cities).id if cities else None,
            )
            for _ in range(count)
        ]

    def generate_news_agencies(self, count: int) -> list[NewsAgency]:
        """Create outlets, ensuring a mix of general and financial specialists.

        V33.10 requires that mix so Economic News and Company News can plausibly
        originate from different sources.
        """
        agencies: list[NewsAgency] = []
        for index in range(count):
            agencies.append(
                NewsAgency(
                    id=self.allocator.next_id(EntityKind.NEWS),
                    name=self.names.news_agency_name(),
                    # Alternate rather than randomise, so a small pool always
                    # contains both kinds.
                    specialises_in_finance=index % 2 == 0,
                )
            )
        return agencies

    def generate_universities(self, count: int, cities: list[City]) -> list[University]:
        universities: list[University] = []
        for _ in range(count):
            city = self.rng.choice(cities) if cities else None
            universities.append(
                University(
                    id=self.allocator.next_id("university"),
                    name=self.names.university_name(city.name if city else None),
                    city_id=city.id if city else None,
                )
            )
        return universities

    def generate_organisations(self, count: int) -> list[Organisation]:
        return [
            Organisation(
                id=self.allocator.next_id("organisation"),
                name=self.names.organisation_name(),
            )
            for _ in range(count)
        ]

    # -- whole world -----------------------------------------------------
    def generate(self, seed: int) -> World:
        """Generate a complete world. Called once per save (V34.6)."""
        counts = {
            "cities": self.config.get_int("world.cities"),
            "companies": self.config.get_int("world.companies"),
            "banks": self.config.get_int("world.banks"),
            "news_agencies": self.config.get_int("world.news_agencies"),
            "universities": self.config.get_int("world.universities"),
            "organisations": self.config.get_int("world.organisations"),
        }

        cities = self.generate_cities(counts["cities"])
        companies, leaders = self.generate_companies(counts["companies"], cities)
        world = World(
            seed=seed,
            cities=cities,
            people=leaders,
            companies=companies,
            banks=self.generate_banks(counts["banks"], cities),
            news_agencies=self.generate_news_agencies(counts["news_agencies"]),
            universities=self.generate_universities(counts["universities"], cities),
            organisations=self.generate_organisations(counts["organisations"]),
        )
        logger.info(
            "Generated world (seed %s): %d companies across %d industries, "
            "%d cities, %d banks.",
            seed,
            len(world.companies),
            len(world.industries_represented),
            len(world.cities),
            len(world.banks),
        )
        return world


def generate_world(
    seed: int,
    *,
    allocator: IdAllocator | None = None,
    config: Config | None = None,
) -> tuple[World, IdAllocator, NameGenerator]:
    """Generate a world from ``seed``.

    Returns the world alongside the allocator and name generator that produced
    it, since both carry state that must be saved so identifiers and names stay
    unique when the world keeps growing during play (V30.6, V34.3).
    """
    rng = Random(seed)
    generator = WorldGenerator(rng, allocator=allocator, config=config)
    world = generator.generate(seed)
    return world, generator.allocator, generator.names
