"""The save file format.

Design Bible V16.18 asks for a structured, human-readable representation
internally, compressed on the way to disk — which both keeps files small
(V16.20) and discourages casual editing. V16.19 permits lightweight
obfuscation alongside it, and is explicit that the aim is to discourage
accidental modification rather than to prevent a determined person from editing
a save. Nothing here is security, and it is not presented as such.

A file is laid out as::

    APEXSAVE\\x01 | 4-byte checksum | obfuscated gzip of UTF-8 JSON

The checksum is what lets Save Validation (V16.13) detect a truncated or
corrupted file before anything tries to interpret it, and Save Recovery (V16.14)
attempt something sensible when it does not match.
"""

from __future__ import annotations

import gzip
import json
import zlib
from dataclasses import asdict, dataclass, field
from typing import Any

from ..values import Money, format_calendar_label, new_save_id, now_iso

# File signature and container revision. The container is separate from the
# save *format* version in the metadata: this changes only if the framing does.
MAGIC = b"APEXSAVE"
CONTAINER_VERSION = 1

# The save format version, raised whenever the shape of the saved state changes
# in a way that needs migrating (V16.15).
SAVE_FORMAT_VERSION = 1

# A fixed key used to obfuscate the compressed bytes (V16.19). Deliberately not
# a secret — its only purpose is to stop a save opening cleanly in a text editor.
_OBFUSCATION_KEY = b"apex-horizon-save"


class SaveFormatError(Exception):
    """Raised when bytes cannot be read as a save file."""


@dataclass
class SaveMetadata:
    """What a save knows about itself (V16.16)."""

    save_id: str = field(default_factory=new_save_id)
    save_format_version: int = SAVE_FORMAT_VERSION
    game_version: str = "0.1.0"
    created: str = field(default_factory=now_iso)
    last_saved: str = field(default_factory=now_iso)
    name: str = "Untitled"
    playtime_seconds: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SaveMetadata:
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)


@dataclass
class SaveSummary:
    """The figures a save slot shows without loading the whole world (V16.9)."""

    money: str = "0"
    net_worth: str = "0"
    company_name: str = ""
    year: int = 1
    month: int = 1
    week: int = 1
    day: int = 1

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> SaveSummary:
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    @property
    def money_value(self) -> Money:
        return Money(self.money)

    @property
    def net_worth_value(self) -> Money:
        return Money(self.net_worth)

    def date_label(self) -> str:
        return format_calendar_label(self.year, self.month, self.week, self.day)


@dataclass
class SaveDocument:
    """A complete save: what it is, what it shows, and the world itself."""

    metadata: SaveMetadata = field(default_factory=SaveMetadata)
    summary: SaveSummary = field(default_factory=SaveSummary)
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "summary": self.summary.to_dict(),
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict) -> SaveDocument:
        return cls(
            metadata=SaveMetadata.from_dict(data.get("metadata", {})),
            summary=SaveSummary.from_dict(data.get("summary", {})),
            state=data.get("state", {}),
        )


def _obfuscate(payload: bytes) -> bytes:
    """XOR the payload against a repeating key.

    Done a whole machine word at a time rather than byte by byte. A save is
    hundreds of kilobytes once the world is populated, and a per-byte generator
    made autosaving the single most expensive thing the simulation did — more
    than every company in the world put together.
    """
    key = _OBFUSCATION_KEY
    repeats = -(-len(payload) // len(key))
    mask = (key * repeats)[: len(payload)]
    return (
        int.from_bytes(payload, "big") ^ int.from_bytes(mask, "big")
    ).to_bytes(len(payload), "big") if payload else b""


# The transform is its own inverse.
_deobfuscate = _obfuscate


def encode(document: SaveDocument) -> bytes:
    """Turn a save document into the bytes written to disk."""
    text = json.dumps(document.to_dict(), separators=(",", ":"), sort_keys=True)
    compressed = gzip.compress(text.encode("utf-8"), compresslevel=6)
    body = _obfuscate(compressed)
    checksum = zlib.crc32(compressed) & 0xFFFFFFFF
    return MAGIC + bytes([CONTAINER_VERSION]) + checksum.to_bytes(4, "big") + body


def decode(raw: bytes, *, verify: bool = True) -> SaveDocument:
    """Read bytes back into a save document.

    ``verify`` is set aside by Save Recovery (V16.14), which tries to salvage a
    file whose checksum no longer matches rather than discarding it outright.
    """
    if len(raw) < len(MAGIC) + 5 or not raw.startswith(MAGIC):
        raise SaveFormatError("This file is not an Apex Horizon save.")
    container = raw[len(MAGIC)]
    if container > CONTAINER_VERSION:
        raise SaveFormatError(
            f"This save was written by a newer version of the game (container {container})."
        )
    expected = int.from_bytes(raw[len(MAGIC) + 1: len(MAGIC) + 5], "big")
    compressed = _deobfuscate(raw[len(MAGIC) + 5:])

    actual = zlib.crc32(compressed) & 0xFFFFFFFF
    if verify and actual != expected:
        raise SaveFormatError("This save file is damaged: its checksum does not match.")

    try:
        text = gzip.decompress(compressed).decode("utf-8")
        data = json.loads(text)
    except (OSError, EOFError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SaveFormatError(f"This save file could not be read: {exc}") from exc
    if not isinstance(data, dict):
        raise SaveFormatError("This save file does not contain a save.")
    return SaveDocument.from_dict(data)


def checksum_matches(raw: bytes) -> bool:
    """Whether a file's contents still match its recorded checksum (V16.13)."""
    try:
        expected = int.from_bytes(raw[len(MAGIC) + 1: len(MAGIC) + 5], "big")
        compressed = _deobfuscate(raw[len(MAGIC) + 5:])
        return (zlib.crc32(compressed) & 0xFFFFFFFF) == expected
    except Exception:
        return False
