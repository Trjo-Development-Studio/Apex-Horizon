"""Tests for naming standards and the name generator (V32, V33, V34.4)."""

from __future__ import annotations

import re
from random import Random

import pytest

from apex_horizon.engine.world import (
    ALL_INDUSTRIES,
    INDUSTRY_NAMING,
    SCOPE_CITY,
    SCOPE_ORGANISATION,
    SCOPE_PERSON,
    Industry,
    NameGenerator,
    naming_for,
    word_pools,
)

ALL_POOLS = {
    name: value
    for name, value in vars(word_pools).items()
    if name.isupper() and isinstance(value, tuple)
}


def generator(seed: int = 1) -> NameGenerator:
    return NameGenerator(Random(seed))


# -- the curated pools themselves (V32.5) ---------------------------------


def test_every_pool_entry_is_plain_ascii():
    # V32.5 requires names readable at a glance and free of meaningless
    # character combinations; a stray non-Latin character in a pool would leak
    # into generated names everywhere.
    for pool_name, entries in ALL_POOLS.items():
        for entry in entries:
            assert entry.isascii(), f"{pool_name} contains non-ASCII entry {entry!r}"


def test_pool_entries_are_non_empty_and_trimmed():
    for pool_name, entries in ALL_POOLS.items():
        for entry in entries:
            assert entry, f"{pool_name} contains an empty entry"
            assert entry == entry.strip(), f"{pool_name} entry {entry!r} has stray whitespace"


def test_pools_contain_no_duplicates():
    for pool_name, entries in ALL_POOLS.items():
        assert len(entries) == len(set(entries)), f"{pool_name} contains duplicates"


def test_design_bible_word_families_are_present():
    # V32.8 lists these thirteen words explicitly.
    expected = {
        "Horizon", "Atlas", "Summit", "Meridian", "Skyline", "Keystone",
        "Evergreen", "Harbor", "Crown", "Frontier", "Prime", "Unity", "Pinnacle",
    }
    assert expected <= set(word_pools.CORPORATE_WORD_FAMILIES)


# -- industry identities (V32.7) ------------------------------------------


def test_all_twenty_industries_exist():
    expected = {
        "Food", "Technology", "Entertainment", "Financial", "Management",
        "Transport", "Energy", "Healthcare", "Construction", "Retail",
        "Manufacturing", "Telecommunications", "Automotive", "Aerospace",
        "Mining", "Shipping", "Pharmaceuticals", "Gaming", "Hospitality", "Media",
    }
    assert {industry.value for industry in ALL_INDUSTRIES} == expected
    assert len(ALL_INDUSTRIES) == 20


def test_every_industry_has_a_documented_identity():
    # V32.7 requires each industry's naming philosophy to be documented and
    # maintained, not left implicit.
    for industry in ALL_INDUSTRIES:
        identity = naming_for(industry)
        assert identity.philosophy.strip()
        assert identity.nouns
        assert identity.patterns
        assert identity.combinations > 0


def test_industry_identities_are_registered_for_every_industry():
    assert set(INDUSTRY_NAMING) == set(ALL_INDUSTRIES)


# -- generated names -------------------------------------------------------

NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z .'&-]*$")


def test_company_names_are_well_formed_across_every_industry():
    names = generator()
    for industry in ALL_INDUSTRIES:
        for _ in range(20):
            name = names.company_name(industry)
            assert name.isascii()
            assert NAME_PATTERN.match(name), f"{industry} produced {name!r}"
            assert name == name.strip()
            assert "{" not in name and "}" not in name


def test_company_names_reflect_their_industry_identity():
    # V32.7: a player should often be able to infer the industry from the name.
    names = generator()
    identity = naming_for(Industry.MINING)
    produced = [names.company_name(Industry.MINING) for _ in range(40)]
    assert all(any(noun in name for noun in identity.nouns) for name in produced)


def test_technology_names_can_be_invented_coinages():
    # V32.7 gives Technology short, modern, invented words.
    names = generator(seed=5)
    produced = [names.company_name(Industry.TECHNOLOGY) for _ in range(60)]
    identity = naming_for(Industry.TECHNOLOGY)
    coinages = [n for n in produced if not any(noun in n for noun in identity.nouns)]
    assert coinages, "Technology should sometimes produce a bare invented name"


def test_partnership_names_never_repeat_a_surname():
    # "Gallagher & Gallagher Partners" reads as generated rather than chosen,
    # failing the professional-tone rule of V32.5.
    names = generator(seed=3)
    partnerships = [
        name
        for _ in range(200)
        if "&" in (name := names.company_name(Industry.MANAGEMENT))
    ]
    assert partnerships, "the partnership pattern should sometimes be chosen"
    for name in partnerships:
        left, _, rest = name.partition(" & ")
        right = rest.split(" ")[0]
        assert left != right, f"repeated surname in {name!r}"


def test_no_industry_places_its_noun_before_the_qualifier():
    # Reversed forms such as "Foods Marigold" or "Masonry Onward" read as
    # generated rather than chosen (V32.5).
    for industry in ALL_INDUSTRIES:
        for pattern in naming_for(industry).patterns:
            if "{noun}" in pattern and "{word}" in pattern:
                assert pattern.index("{noun}") > pattern.index("{word}"), (
                    f"{industry} pattern {pattern!r} puts the noun first"
                )
            if "{noun}" in pattern and "{surname}" in pattern:
                assert pattern.index("{noun}") > pattern.index("{surname}"), (
                    f"{industry} pattern {pattern!r} puts the noun first"
                )


def test_person_city_and_institution_names_are_well_formed():
    names = generator()
    for factory in (
        names.person_name,
        names.city_name,
        names.bank_name,
        names.news_agency_name,
        names.organisation_name,
        names.fund_name,
    ):
        for _ in range(20):
            name = factory()
            assert name.isascii() and name.strip() == name and name


def test_university_name_uses_its_city():
    names = generator()
    produced = [names.university_name("Northgate") for _ in range(10)]
    assert any("Northgate" in name for name in produced)


def test_university_name_without_a_city_still_works():
    assert generator().university_name(None)


def test_fund_name_can_carry_the_house_name():
    name = generator().fund_name(house="Apex Horizon Capital")
    assert name.startswith("Apex Horizon Capital ")


# -- uniqueness (V33.3, V34.3) --------------------------------------------


def test_generated_names_are_unique_within_a_scope():
    names = generator()
    produced = [names.company_name(Industry.RETAIL) for _ in range(200)]
    assert len(produced) == len(set(produced))


def test_companies_and_banks_share_one_uniqueness_scope():
    # A world containing a company and a bank with the same name would read as
    # a bug, so organisation-like entities share a scope.
    names = generator()
    company_names = {names.company_name(Industry.FINANCIAL) for _ in range(100)}
    bank_names = {names.bank_name() for _ in range(50)}
    assert not (company_names & bank_names)


def test_people_and_cities_use_separate_scopes():
    names = generator()
    names.person_name()
    used = names.state()["used"]
    assert names.is_used(SCOPE_PERSON, used[SCOPE_PERSON][0])
    names.city_name()
    used = names.state()["used"]
    assert used[SCOPE_CITY]
    # Scopes are tracked independently.
    assert used[SCOPE_PERSON] != used[SCOPE_CITY]


def test_exhausted_pool_degrades_to_a_plausible_qualifier():
    # Forced collision: a factory that can only ever produce one name.
    names = generator()
    first = names._unique(SCOPE_ORGANISATION, lambda: "Atlas Foods", ("Group", "International"))
    second = names._unique(SCOPE_ORGANISATION, lambda: "Atlas Foods", ("Group", "International"))
    third = names._unique(SCOPE_ORGANISATION, lambda: "Atlas Foods", ("Group", "International"))
    fourth = names._unique(SCOPE_ORGANISATION, lambda: "Atlas Foods", ("Group", "International"))
    assert first == "Atlas Foods"
    assert second == "Atlas Foods Group"
    assert third == "Atlas Foods International"
    # Qualifiers exhausted: falls back to a numeric suffix rather than looping.
    assert fourth == "Atlas Foods 2"
    assert len({first, second, third, fourth}) == 4


# -- determinism (V15.11, V34.6) ------------------------------------------


def test_same_seed_produces_the_same_names():
    def sample(seed: int) -> list[str]:
        names = generator(seed)
        return [names.company_name(Industry.ENERGY) for _ in range(25)]

    assert sample(42) == sample(42)
    assert sample(42) != sample(43)


def test_state_round_trip_preserves_uniqueness():
    names = generator()
    produced = {names.company_name(Industry.GAMING) for _ in range(30)}

    # A world that keeps generating names after loading must not reissue one.
    restored = NameGenerator.from_state(Random(999), names.state())
    later = {restored.company_name(Industry.GAMING) for _ in range(30)}
    assert not (produced & later)


def test_from_state_tolerates_missing_state():
    assert NameGenerator.from_state(Random(1), None).city_name()


@pytest.mark.parametrize("industry", list(ALL_INDUSTRIES))
def test_each_industry_can_produce_many_distinct_names(industry: Industry):
    # V33.3: the pool must be large enough that a playthrough never exhausts it.
    names = generator(seed=7)
    produced = {names.company_name(industry) for _ in range(150)}
    assert len(produced) == 150


def test_the_name_stream_position_is_saved():
    """V15.11: names drawn after loading match an uninterrupted run."""
    names = generator()
    for _ in range(5):
        names.person_name()

    restored = NameGenerator.from_state(Random(0), names.state())

    assert [restored.person_name() for _ in range(5)] == [
        names.person_name() for _ in range(5)
    ]


def test_a_save_written_before_the_stream_was_recorded_still_loads():
    """V16.15: an older save holds only the used names, at the top level."""
    old_format = {SCOPE_PERSON: ["Ada Lovelace"], SCOPE_ORGANISATION: ["Atlas Foods"]}

    names = NameGenerator.from_state(Random(1), old_format)

    assert names.is_used(SCOPE_PERSON, "Ada Lovelace")
    assert names.is_used(SCOPE_ORGANISATION, "Atlas Foods")
    assert "rng_state" not in names.state()["used"]
