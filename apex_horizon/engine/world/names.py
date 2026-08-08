"""Name generation.

Design Bible V34.4 requires named entities to be drawn from the curated datasets
of V32 and V33 rather than assembled through unconstrained procedural
generation, so that the world keeps the handcrafted feeling described in V32.4
even though any given save's selection is effectively random.

Uniqueness is enforced per save (V33.3, V34.3). Names are grouped into three
uniqueness scopes rather than one per category, so that a world never contains,
say, a company and a bank with identical names:

``organisation``
    Companies, banks, news agencies, universities, organisations, and funds.
``person``
    CEOs and employees, who come from one shared population (V33.6).
``city``
    Places.

V33.6 notes that exact uniqueness is not required for employees given their
expected scale; the generator nevertheless keeps them unique wherever practical,
falling back to a plausible qualifier rather than ever returning a duplicate.
"""

from __future__ import annotations

from collections.abc import Callable
from random import Random

from .industries import Industry, naming_for
from .word_pools import (
    BANK_SUFFIXES,
    CITY_ROOTS,
    CITY_SUFFIXES,
    CORPORATE_WORD_FAMILIES,
    FAMILY_NAMES,
    FUND_STRATEGIES,
    FUND_VEHICLES,
    GIVEN_NAMES,
    INVENTED_PREFIXES,
    INVENTED_SUFFIXES,
    NEWS_AGENCY_PREFIXES,
    NEWS_AGENCY_SUFFIXES,
    ORGANISATION_BODIES,
    ORGANISATION_DOMAINS,
    ORGANISATION_SCOPES,
    UNIVERSITY_FORMS,
)

# Uniqueness scopes (see module docstring).
SCOPE_ORGANISATION = "organisation"
SCOPE_PERSON = "person"
SCOPE_CITY = "city"

# How many times to re-roll for an unused name before falling back.
MAX_ATTEMPTS = 200

# Neutral qualifiers appended if the pool ever fails to produce an unused name.
# Chosen so the result still reads as a real organisation rather than a
# numbered placeholder.
ORGANISATION_QUALIFIERS = ("Group", "International", "Holdings", "Worldwide", "Partners")


class NameGenerator:
    """Composes unique names for one save's world.

    All randomness comes from the injected generator, so a world regenerated
    from the same seed produces identical names (V15.11, V34.6).
    """

    def __init__(self, rng: Random, used: dict[str, set[str]] | None = None):
        self._rng = rng
        self._used: dict[str, set[str]] = {
            SCOPE_ORGANISATION: set(),
            SCOPE_PERSON: set(),
            SCOPE_CITY: set(),
        }
        for scope, names in (used or {}).items():
            self._used.setdefault(scope, set()).update(names)

    # -- uniqueness ------------------------------------------------------
    def _unique(
        self,
        scope: str,
        factory: Callable[[], str],
        qualifiers: tuple[str, ...] = (),
    ) -> str:
        """Return an unused name from ``factory`` and record it as used."""
        used = self._used.setdefault(scope, set())
        for _ in range(MAX_ATTEMPTS):
            candidate = factory()
            if candidate not in used:
                used.add(candidate)
                return candidate

        # The pools are far larger than any single playthrough consumes, so
        # reaching here means an unusually small pool or an unusually large
        # world. Degrade gracefully rather than failing or looping forever.
        base = factory()
        for qualifier in qualifiers:
            candidate = f"{base} {qualifier}"
            if candidate not in used:
                used.add(candidate)
                return candidate
        index = 2
        while f"{base} {index}" in used:
            index += 1
        candidate = f"{base} {index}"
        used.add(candidate)
        return candidate

    def is_used(self, scope: str, name: str) -> bool:
        return name in self._used.get(scope, set())

    # -- building blocks -------------------------------------------------
    def _word(self) -> str:
        return self._rng.choice(CORPORATE_WORD_FAMILIES)

    def _invented(self) -> str:
        return self._rng.choice(INVENTED_PREFIXES) + self._rng.choice(INVENTED_SUFFIXES)

    def _surname(self) -> str:
        return self._rng.choice(FAMILY_NAMES)

    def _render(self, pattern: str, nouns: tuple[str, ...]) -> str:
        """Fill a naming pattern's placeholders.

        Each occurrence is filled independently, so a pattern using the same
        placeholder twice — such as the partnership form "{surname} & {surname}
        {noun}" — never repeats a single value as "Gallagher & Gallagher".
        """
        sources = {
            "{word}": self._word,
            "{noun}": lambda: self._rng.choice(nouns),
            "{invented}": self._invented,
            "{surname}": self._surname,
        }
        for placeholder, source in sources.items():
            seen: list[str] = []
            while placeholder in pattern:
                # Draw a value distinct from the ones already used in this name.
                value = source()
                for _ in range(20):
                    if value not in seen:
                        break
                    value = source()
                seen.append(value)
                pattern = pattern.replace(placeholder, value, 1)
        return pattern

    # -- entity names ----------------------------------------------------
    def company_name(self, industry: Industry) -> str:
        """A company name reflecting its industry's identity (V32.7).

        The industry is chosen before the name so the name can express it, as
        required by V33.3.
        """
        identity = naming_for(industry)

        def build() -> str:
            return self._render(self._rng.choice(identity.patterns), identity.nouns)

        return self._unique(SCOPE_ORGANISATION, build, ORGANISATION_QUALIFIERS)

    def person_name(self) -> str:
        """A personal name for a CEO or employee (V33.5, V33.6)."""

        def build() -> str:
            return f"{self._rng.choice(GIVEN_NAMES)} {self._rng.choice(FAMILY_NAMES)}"

        # A middle initial is the natural way two real people sharing a name are
        # distinguished, so it is used before any numeric fallback.
        initials = tuple(f"{letter}." for letter in "ABCDEFGHJKLMNPRSTVW")
        return self._unique(SCOPE_PERSON, build, initials)

    def city_name(self) -> str:
        """A city name (V33.7): invented roots with generic geographic suffixes."""

        def build() -> str:
            return self._rng.choice(CITY_ROOTS) + self._rng.choice(CITY_SUFFIXES)

        return self._unique(SCOPE_CITY, build)

    def bank_name(self) -> str:
        """A bank name in the Financial register (V33.4)."""

        def build() -> str:
            return f"{self._word()} {self._rng.choice(BANK_SUFFIXES)}"

        return self._unique(SCOPE_ORGANISATION, build, ORGANISATION_QUALIFIERS)

    def news_agency_name(self) -> str:
        """A news outlet name in the Media register (V33.10)."""

        def build() -> str:
            if self._rng.random() < 0.5:
                prefix = self._rng.choice(NEWS_AGENCY_PREFIXES)
            else:
                prefix = self._word()
            return f"The {prefix} {self._rng.choice(NEWS_AGENCY_SUFFIXES)}"

        return self._unique(SCOPE_ORGANISATION, build, ORGANISATION_QUALIFIERS)

    def university_name(self, place: str | None = None) -> str:
        """A university name (V33.8), optionally tied to a city."""

        def build() -> str:
            form = self._rng.choice(UNIVERSITY_FORMS)
            if "{place}" in form and place is None:
                form = "{word} University"
            return form.replace("{place}", place or "").replace("{word}", self._word())

        return self._unique(SCOPE_ORGANISATION, build)

    def organisation_name(self) -> str:
        """A regulator or industry body (V33.11), in a formal institutional register."""

        def build() -> str:
            return (
                f"{self._rng.choice(ORGANISATION_SCOPES)} "
                f"{self._rng.choice(ORGANISATION_DOMAINS)} "
                f"{self._rng.choice(ORGANISATION_BODIES)}"
            )

        return self._unique(SCOPE_ORGANISATION, build)

    def fund_name(self, house: str | None = None) -> str:
        """An investment fund name (V33.9).

        Funds are financial products rather than standalone companies, so they
        may reuse the corporate word families (V32.8). Created dynamically at
        the moment a fund is founded rather than pre-generated (V35.6).
        """

        def build() -> str:
            prefix = house or self._word()
            return (
                f"{prefix} {self._rng.choice(FUND_STRATEGIES)} "
                f"{self._rng.choice(FUND_VEHICLES)}"
            )

        return self._unique(SCOPE_ORGANISATION, build)

    # -- persistence -----------------------------------------------------
    def state(self) -> dict[str, list[str]]:
        """Used names, saved with the world so uniqueness survives a reload."""
        return {scope: sorted(names) for scope, names in self._used.items()}

    @classmethod
    def from_state(cls, rng: Random, state: dict[str, list[str]] | None) -> NameGenerator:
        used = {scope: set(names) for scope, names in (state or {}).items()}
        return cls(rng, used=used)
