"""World entities.

These are the persistent records produced by world generation. Each carries the
unique internal identifier required by V30.6, kept distinct from its display
name so entities can be renamed and cross-referenced without ambiguity.

``Company`` is deliberately the single company structure for the whole game.
V15.4 allows only one company data model, V26.10 requires AI companies to be
instances of that same structure differing only in who makes their decisions,
and V12.23 requires a subsidiary to be an ownership wrapper around it rather
than a separate model. Later milestones extend this record with market and
financial state rather than introducing a parallel one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .industries import Industry


@dataclass
class City:
    """A place companies, universities and news events can belong to (V33.7)."""

    id: str
    name: str


@dataclass
class Person:
    """A named person — a CEO today, an employee later (V33.5, V33.6)."""

    id: str
    name: str


@dataclass
class Company:
    """A company in the world (V33.3).

    Every company that exists is entirely fictional (V24.3), belongs to exactly
    one industry, and is generated with its industry chosen first so its name
    can express that industry's identity (V32.7).
    """

    id: str
    name: str
    industry: Industry
    headquarters_id: str | None = None
    ceo_id: str | None = None
    # Set when the company is acquired; V12.23 keeps a subsidiary as an
    # ownership reference on the same structure rather than a separate model.
    owner_id: str | None = None

    @property
    def is_subsidiary(self) -> bool:
        return self.owner_id is not None


@dataclass
class Bank:
    """A lender providing the loans of V17.13 (V33.4)."""

    id: str
    name: str
    headquarters_id: str | None = None


@dataclass
class NewsAgency:
    """A byline for the News System, so news comes from within the world (V33.10)."""

    id: str
    name: str
    # Some outlets are general, others specialise in financial reporting, so
    # Company News and Economic News can plausibly come from different sources.
    specialises_in_finance: bool = False


@dataclass
class University:
    """An institution providing texture for news and future employee backgrounds (V33.8)."""

    id: str
    name: str
    city_id: str | None = None


@dataclass
class Organisation:
    """A regulator or industry body implied by the governments of V24.4 (V33.11)."""

    id: str
    name: str


@dataclass
class World:
    """Everything generated once, at save creation, for one independent world.

    V16.12 makes every save an independent alternative world with its own
    companies and banks; V34.6 then hands over to the Deterministic Simulation
    guarantee of V15.11, so whatever was generated here must remain exactly
    consistent across every later load of that save.
    """

    seed: int
    cities: list[City] = field(default_factory=list)
    people: list[Person] = field(default_factory=list)
    companies: list[Company] = field(default_factory=list)
    banks: list[Bank] = field(default_factory=list)
    news_agencies: list[NewsAgency] = field(default_factory=list)
    universities: list[University] = field(default_factory=list)
    organisations: list[Organisation] = field(default_factory=list)

    def company_by_id(self, company_id: str) -> Company | None:
        return next((c for c in self.companies if c.id == company_id), None)

    def person_by_id(self, person_id: str) -> Person | None:
        return next((p for p in self.people if p.id == person_id), None)

    def city_by_id(self, city_id: str) -> City | None:
        return next((c for c in self.cities if c.id == city_id), None)

    def companies_in(self, industry: Industry) -> list[Company]:
        return [company for company in self.companies if company.industry is industry]

    @property
    def industries_represented(self) -> set[Industry]:
        return {company.industry for company in self.companies}

    # -- persistence ------------------------------------------------------
    def state(self) -> dict:
        """Serialisable world state (V16.11).

        The world is generated once from a seed (V34.6), but it keeps growing
        during play as new companies list on the market, so the entities
        themselves are saved rather than only the seed that started them.
        """
        return {
            "seed": self.seed,
            "cities": [{"id": c.id, "name": c.name} for c in self.cities],
            "people": [{"id": p.id, "name": p.name} for p in self.people],
            "companies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "industry": c.industry.value,
                    "headquarters_id": c.headquarters_id,
                    "ceo_id": c.ceo_id,
                    "owner_id": c.owner_id,
                }
                for c in self.companies
            ],
            "banks": [
                {"id": b.id, "name": b.name, "headquarters_id": b.headquarters_id}
                for b in self.banks
            ],
            "news_agencies": [
                {"id": a.id, "name": a.name,
                 "specialises_in_finance": a.specialises_in_finance}
                for a in self.news_agencies
            ],
            "universities": [
                {"id": u.id, "name": u.name, "city_id": u.city_id}
                for u in self.universities
            ],
            "organisations": [{"id": o.id, "name": o.name} for o in self.organisations],
        }

    @classmethod
    def from_state(cls, data: dict) -> World:
        """Rebuild a world saved by :meth:`state`."""
        industries = {industry.value: industry for industry in Industry}
        return cls(
            seed=int(data.get("seed", 0)),
            cities=[City(**entry) for entry in data.get("cities", [])],
            people=[Person(**entry) for entry in data.get("people", [])],
            companies=[
                Company(
                    id=entry["id"],
                    name=entry["name"],
                    industry=industries[entry["industry"]],
                    headquarters_id=entry.get("headquarters_id"),
                    ceo_id=entry.get("ceo_id"),
                    owner_id=entry.get("owner_id"),
                )
                for entry in data.get("companies", [])
            ],
            banks=[Bank(**entry) for entry in data.get("banks", [])],
            news_agencies=[NewsAgency(**entry) for entry in data.get("news_agencies", [])],
            universities=[University(**entry) for entry in data.get("universities", [])],
            organisations=[Organisation(**entry) for entry in data.get("organisations", [])],
        )
