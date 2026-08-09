"""Tests for world generation (Design Bible V34, V33, V16.12)."""

from __future__ import annotations

from random import Random

from apex_horizon.engine.config import get_config
from apex_horizon.engine.values import IdAllocator, parse_id
from apex_horizon.engine.world import ALL_INDUSTRIES, WorldGenerator, generate_world


def build(seed: int = 2026):
    world, allocator, names = generate_world(seed)
    return world, allocator, names


def test_world_matches_the_configured_size():
    config = get_config()
    world, _, _ = build()
    assert len(world.companies) == config.get_int("world.companies")
    assert len(world.cities) == config.get_int("world.cities")
    assert len(world.banks) == config.get_int("world.banks")
    assert len(world.news_agencies) == config.get_int("world.news_agencies")
    assert len(world.universities) == config.get_int("world.universities")
    assert len(world.organisations) == config.get_int("world.organisations")


def test_every_industry_is_represented():
    # V33.3: distributed across every industry rather than concentrated in a
    # small subset.
    world, _, _ = build()
    assert world.industries_represented == set(ALL_INDUSTRIES)


def test_industry_distribution_is_even():
    world, _, _ = build()
    counts = [len(world.companies_in(industry)) for industry in ALL_INDUSTRIES]
    # Round-robin dealing keeps every industry within one company of the others.
    assert max(counts) - min(counts) <= 1


def test_company_names_are_unique_within_the_save():
    # V33.3 / V16.12: no two companies in one save may share a name.
    world, _, _ = build()
    names = [company.name for company in world.companies]
    assert len(names) == len(set(names))


def test_no_name_is_reused_across_organisation_categories():
    world, _, _ = build()
    names = (
        [c.name for c in world.companies]
        + [b.name for b in world.banks]
        + [a.name for a in world.news_agencies]
        + [u.name for u in world.universities]
        + [o.name for o in world.organisations]
    )
    assert len(names) == len(set(names))


def test_city_and_person_names_are_unique():
    world, _, _ = build()
    assert len({city.name for city in world.cities}) == len(world.cities)
    assert len({person.name for person in world.people}) == len(world.people)


def test_every_company_has_an_identifier_industry_ceo_and_home():
    world, _, _ = build()
    for company in world.companies:
        kind, number = parse_id(company.id)
        assert kind == "company" and number > 0
        assert company.industry in ALL_INDUSTRIES
        assert company.ceo_id is not None
        assert world.person_by_id(company.ceo_id) is not None
        assert company.headquarters_id is not None
        assert world.city_by_id(company.headquarters_id) is not None
        assert not company.is_subsidiary


def test_identifiers_are_unique_across_the_world():
    world, _, _ = build()
    ids = (
        [c.id for c in world.companies]
        + [p.id for p in world.people]
        + [c.id for c in world.cities]
        + [b.id for b in world.banks]
        + [a.id for a in world.news_agencies]
        + [u.id for u in world.universities]
        + [o.id for o in world.organisations]
    )
    assert len(ids) == len(set(ids))


def test_each_company_has_its_own_ceo():
    world, _, _ = build()
    ceo_ids = [company.ceo_id for company in world.companies]
    assert len(ceo_ids) == len(set(ceo_ids))


def test_news_agencies_mix_general_and_financial_outlets():
    # V33.10: Economic News and Company News should be able to come from
    # different sources.
    world, _, _ = build()
    specialisations = {agency.specialises_in_finance for agency in world.news_agencies}
    assert specialisations == {True, False}


def test_universities_are_placed_in_generated_cities():
    world, _, _ = build()
    city_ids = {city.id for city in world.cities}
    for university in world.universities:
        assert university.city_id in city_ids


def test_banks_are_headquartered_in_generated_cities():
    world, _, _ = build()
    city_ids = {city.id for city in world.cities}
    assert all(bank.headquarters_id in city_ids for bank in world.banks)


# -- determinism and independence (V15.11, V34.2, V34.6) ------------------


def test_same_seed_regenerates_an_identical_world():
    first, _, _ = build(1234)
    second, _, _ = build(1234)
    assert [c.name for c in first.companies] == [c.name for c in second.companies]
    assert [c.industry for c in first.companies] == [c.industry for c in second.companies]
    assert [c.id for c in first.companies] == [c.id for c in second.companies]
    assert [c.name for c in first.cities] == [c.name for c in second.cities]
    assert [p.name for p in first.people] == [p.name for p in second.people]


def test_different_seeds_produce_different_worlds():
    # V34.2 / V34.5: each save draws its own combination from the shared pool.
    first, _, _ = build(1)
    second, _, _ = build(2)
    assert [c.name for c in first.companies] != [c.name for c in second.companies]
    overlap = {c.name for c in first.companies} & {c.name for c in second.companies}
    # Some overlap is natural from a shared pool, but the worlds must not match.
    assert len(overlap) < len(first.companies) // 2


def test_world_records_its_seed():
    world, _, _ = build(4321)
    assert world.seed == 4321


def test_generation_state_supports_continued_growth():
    # The allocator and name generator carry state that must be saved so the
    # market can keep creating companies later without collisions (V30.6, V34.3).
    world, allocator, names = build()
    existing = {company.name for company in world.companies}

    generator = WorldGenerator(Random(7), allocator=allocator, names=names)
    later, _ = generator.generate_companies(10, world.cities)
    assert not ({company.name for company in later} & existing)
    assert not ({company.id for company in later} & {c.id for c in world.companies})


def test_supplied_allocator_is_used():
    allocator = IdAllocator()
    allocator.next_id("company")
    world, _, _ = generate_world(5, allocator=allocator)
    # Identifiers continue from the allocator's existing counter.
    assert world.companies[0].id == "company-000002"


def test_lookup_helpers():
    world, _, _ = build()
    company = world.companies[0]
    assert world.company_by_id(company.id) is company
    assert world.company_by_id("company-999999") is None
