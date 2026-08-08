"""Tests for entity identifiers (V30.6) and real-world timestamps (V30.5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from apex_horizon.engine.values import (
    EntityKind,
    IdAllocator,
    new_save_id,
    now_iso,
    parse_id,
    parse_iso,
    to_iso,
)


def test_identifiers_are_sequential_per_kind():
    allocator = IdAllocator()
    assert allocator.next_id(EntityKind.COMPANY) == "company-000001"
    assert allocator.next_id(EntityKind.COMPANY) == "company-000002"
    # Each kind counts independently.
    assert allocator.next_id(EntityKind.EMPLOYEE) == "employee-000001"


def test_identifiers_are_unique_across_many_allocations():
    allocator = IdAllocator()
    issued = {allocator.next_id(EntityKind.EMPLOYEE) for _ in range(500)}
    assert len(issued) == 500
    assert allocator.issued(EntityKind.EMPLOYEE) == 500


def test_allocation_is_reproducible():
    # Determinism (V15.11): the same sequence of calls yields the same ids.
    first = IdAllocator()
    second = IdAllocator()
    kinds = [EntityKind.COMPANY, EntityKind.FUND, EntityKind.COMPANY]
    assert [first.next_id(k) for k in kinds] == [second.next_id(k) for k in kinds]


def test_state_round_trip_continues_the_sequence():
    allocator = IdAllocator()
    allocator.next_id(EntityKind.COMPANY)
    allocator.next_id(EntityKind.COMPANY)

    # Counters travel with the save so identifiers never collide after loading.
    restored = IdAllocator.from_state(allocator.state())
    assert restored.next_id(EntityKind.COMPANY) == "company-000003"


def test_from_state_tolerates_missing_state():
    assert IdAllocator.from_state(None).next_id(EntityKind.BANK) == "bank-000001"


def test_state_is_a_copy():
    allocator = IdAllocator()
    allocator.next_id(EntityKind.COMPANY)
    state = allocator.state()
    allocator.next_id(EntityKind.COMPANY)
    assert state[EntityKind.COMPANY] == 1


def test_reset_clears_counters():
    allocator = IdAllocator()
    allocator.next_id(EntityKind.COMPANY)
    allocator.reset()
    assert allocator.next_id(EntityKind.COMPANY) == "company-000001"


def test_empty_kind_is_rejected():
    with pytest.raises(ValueError):
        IdAllocator().next_id("")


def test_parse_id_round_trip():
    identifier = IdAllocator().next_id(EntityKind.SUBSIDIARY)
    assert parse_id(identifier) == (EntityKind.SUBSIDIARY, 1)


def test_parse_id_rejects_malformed_identifiers():
    for bad in ("company", "company-", "-000001", "company-abc"):
        with pytest.raises(ValueError):
            parse_id(bad)


def test_save_ids_are_unique():
    assert new_save_id() != new_save_id()
    assert len(new_save_id()) == 32


def test_timestamps_are_iso_utc():
    moment = datetime(2026, 8, 8, 12, 30, 0, tzinfo=UTC)
    assert to_iso(moment) == "2026-08-08T12:30:00+00:00"
    assert parse_iso(to_iso(moment)) == moment


def test_naive_timestamps_are_treated_as_utc():
    # An older save must never fail to load because of a missing offset (V16.15).
    naive = datetime(2026, 8, 8, 12, 30, 0)
    assert to_iso(naive).endswith("+00:00")
    assert parse_iso("2026-08-08T12:30:00").tzinfo is not None


def test_non_utc_input_is_normalised():
    offset = timezone(timedelta(hours=2))
    moment = datetime(2026, 8, 8, 14, 30, 0, tzinfo=offset)
    assert to_iso(moment) == "2026-08-08T12:30:00+00:00"


def test_now_iso_is_parseable_and_current():
    parsed = parse_iso(now_iso())
    assert abs((datetime.now(UTC) - parsed).total_seconds()) < 60
