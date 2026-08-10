"""The save file format, validation, repair and migration."""

from __future__ import annotations

import json

import pytest
from save_support import sample_document

from apex_horizon.engine.save import (
    SAVE_FORMAT_VERSION,
    SaveDocument,
    SaveFormatError,
    decode,
    encode,
    read_save,
    repair,
    validate,
)
from apex_horizon.engine.save import validation as validation_module
from apex_horizon.engine.save.format import MAGIC

# -- the file format (V16.18 - V16.20) ------------------------------------


def test_a_save_round_trips():
    document = sample_document()
    restored = decode(encode(document))
    assert restored.metadata.name == "Meridian Capital"
    assert restored.summary.year == 3
    assert restored.state == document.state


def test_saves_are_compressed_and_not_plain_text():
    # V16.18: compression keeps files small and discourages casual editing.
    document = sample_document()
    document.state["market"] = {f"listing-{i}": {"price": "123.45"} for i in range(400)}
    raw = encode(document)
    plain = json.dumps(document.to_dict()).encode()
    assert len(raw) < len(plain) / 2
    assert b"listing-1" not in raw


def test_a_save_is_recognisable_and_versioned():
    raw = encode(sample_document())
    assert raw.startswith(MAGIC)
    assert decode(raw).metadata.save_format_version == SAVE_FORMAT_VERSION


def test_corruption_is_detected(tmp_path):
    # V16.13: an invalid save must never silently load.
    raw = bytearray(encode(sample_document()))
    raw[-5] ^= 0xFF
    with pytest.raises(SaveFormatError, match="damaged"):
        decode(bytes(raw))


def test_a_truncated_file_is_rejected():
    raw = encode(sample_document())[:20]
    with pytest.raises(SaveFormatError):
        decode(raw)


def test_a_foreign_file_is_rejected():
    with pytest.raises(SaveFormatError, match="not an Apex Horizon save"):
        decode(b"just some other file entirely")


def test_a_newer_container_is_refused():
    raw = bytearray(encode(sample_document()))
    raw[len(MAGIC)] = 99
    with pytest.raises(SaveFormatError, match="newer version"):
        decode(bytes(raw))


def test_metadata_carries_what_volume_16_16_requires():
    metadata = decode(encode(sample_document())).metadata
    assert metadata.save_id
    assert metadata.game_version
    assert metadata.created and metadata.last_saved
    assert isinstance(metadata.save_format_version, int)


# -- validation, repair and migration (V16.13 - V16.15) -------------------


def test_a_complete_save_validates():
    assert validate(sample_document()).valid


def test_missing_systems_are_reported():
    document = sample_document()
    del document.state["market"]
    result = validate(document)
    assert not result.valid
    assert "market" in result.describe()


def test_wrong_types_are_reported():
    document = sample_document()
    document.state["economy"] = "not a mapping"
    assert not validate(document).valid


def test_a_save_from_a_newer_game_is_refused():
    document = sample_document()
    document.metadata.save_format_version = SAVE_FORMAT_VERSION + 5
    assert "newer version" in validate(document).describe()


def test_repair_fills_in_what_it_safely_can():
    document = sample_document()
    document.metadata.save_id = ""
    document.state["market"] = 42
    repaired, notes = repair(document)
    assert repaired.metadata.save_id
    assert notes
    assert "market" not in repaired.state


def test_migration_upgrades_an_older_save(monkeypatch):
    # V16.15: older saves are migrated automatically.
    monkeypatch.setitem(validation_module.MIGRATIONS, 0,
                        lambda doc: _add_marker(doc))
    document = sample_document()
    document.metadata.save_format_version = 0
    outcome = read_save(encode(document))
    assert outcome.ok
    assert outcome.document is not None
    assert outcome.document.state["migrated"] is True
    assert outcome.document.metadata.save_format_version == SAVE_FORMAT_VERSION


def _add_marker(document: SaveDocument) -> SaveDocument:
    document.state["migrated"] = True
    return document


def test_an_unmigratable_save_is_reported_rather_than_loaded():
    document = sample_document()
    document.metadata.save_format_version = 0  # no migration registered
    outcome = read_save(encode(document))
    assert not outcome.ok
    assert "cannot be upgraded" in outcome.describe()


def _with_broken_checksum() -> bytes:
    """A save whose integrity check fails but whose contents are still intact."""
    raw = bytearray(encode(sample_document()))
    raw[len(MAGIC) + 1] ^= 0xFF
    return bytes(raw)


def test_a_damaged_save_asks_before_loading():
    # V16.14: if repair does not succeed the player is asked, not refused.
    outcome = read_save(_with_broken_checksum())
    assert not outcome.ok
    assert outcome.needs_confirmation
    assert outcome.document is not None  # contents were salvaged


def test_a_damaged_save_can_be_loaded_on_request():
    outcome = read_save(_with_broken_checksum(), allow_damaged=True)
    assert outcome.ok
    assert "damaged" in outcome.describe()
    assert outcome.document is not None
    assert outcome.document.metadata.name == "Meridian Capital"


def test_a_save_whose_contents_are_destroyed_cannot_be_salvaged():
    # Corrupting the compressed body itself is beyond repair, and is reported
    # rather than guessed at.
    raw = bytearray(encode(sample_document()))
    raw[-5] ^= 0xFF
    outcome = read_save(bytes(raw))
    assert not outcome.ok
    assert outcome.document is None
    assert "damaged" in outcome.describe()


def test_unreadable_bytes_cannot_be_salvaged():
    outcome = read_save(MAGIC + b"\x01" + b"\x00" * 4 + b"garbage")
    assert not outcome.ok
    assert outcome.document is None
