"""Save slots on disk.

Design Bible V16.8 gives the player five manual slots, each an entirely separate
world (V16.12), alongside a single rolling autosave that each new autosave
replaces (V16.7). V16.9 lists what a slot must show without loading it, which is
why every file carries its own summary.

Files are written atomically — to a temporary name, then moved into place — so
an interruption mid-write can never destroy the save that already existed. That
is what turns V16.30's corrupted-mid-write case from lost progress into, at
worst, a lost autosave.

All saves live in one flat directory with stable names, which is what allows the
Steam Cloud support V16.23 asks for to be added later without redesign.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from ..logging_setup import get_logger
from ..paths import save_dir
from .format import SaveDocument, SaveMetadata, SaveSummary, decode, encode

logger = get_logger(__name__)

AUTOSAVE_SLOT = "autosave"
SAVE_SUFFIX = ".ahsave"


@dataclass
class SlotInfo:
    """What a save slot shows the player before loading it (V16.9)."""

    slot: str
    path: Path
    exists: bool
    metadata: SaveMetadata | None = None
    summary: SaveSummary | None = None
    damaged: bool = False

    @property
    def is_autosave(self) -> bool:
        return self.slot == AUTOSAVE_SLOT

    @property
    def label(self) -> str:
        if self.is_autosave:
            return "Autosave"
        return f"Slot {self.slot}"

    def describe(self) -> str:
        if not self.exists:
            return "Empty"
        if self.damaged or self.summary is None or self.metadata is None:
            return "Damaged save"
        return (
            f"{self.metadata.name} · {self.summary.date_label()} · "
            f"{self.summary.net_worth_value.format(decimals=0)}"
        )


class SaveStore:
    """Reads and writes the save files in one directory."""

    def __init__(self, directory: Path | None = None, *, manual_slots: int = 5):
        self.directory = Path(directory) if directory else save_dir()
        self.manual_slots = manual_slots

    # -- locations ---------------------------------------------------------
    def path_for(self, slot: str | int) -> Path:
        name = AUTOSAVE_SLOT if str(slot) == AUTOSAVE_SLOT else f"slot{int(slot)}"
        return self.directory / f"{name}{SAVE_SUFFIX}"

    def slot_names(self) -> list[str]:
        return [str(index) for index in range(1, self.manual_slots + 1)] + [AUTOSAVE_SLOT]

    # -- reading -----------------------------------------------------------
    def info(self, slot: str | int) -> SlotInfo:
        """Describe a slot without loading its world (V16.9)."""
        path = self.path_for(slot)
        if not path.exists():
            return SlotInfo(slot=str(slot), path=path, exists=False)
        try:
            document = decode(path.read_bytes())
            return SlotInfo(str(slot), path, True, document.metadata, document.summary)
        except Exception:
            # A slot that cannot be summarised is shown as damaged rather than
            # hidden: the player should know it is there (V16.14).
            logger.warning("Save slot %s could not be summarised.", slot)
            return SlotInfo(str(slot), path, True, damaged=True)

    def list_slots(self) -> list[SlotInfo]:
        return [self.info(slot) for slot in self.slot_names()]

    def read(self, slot: str | int) -> bytes:
        return self.path_for(slot).read_bytes()

    def exists(self, slot: str | int) -> bool:
        return self.path_for(slot).exists()

    # -- writing -----------------------------------------------------------
    def write(self, slot: str | int, document: SaveDocument) -> Path:
        """Write a save atomically, so an interruption cannot destroy the old one."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(slot)
        temporary = path.with_suffix(path.suffix + ".tmp")
        payload = encode(document)
        with open(temporary, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        logger.info("Saved %s (%d bytes).", path.name, len(payload))
        return path

    def delete(self, slot: str | int) -> bool:
        path = self.path_for(slot)
        if path.exists():
            path.unlink()
            return True
        return False

    # -- export and import (V16.21, V16.22) --------------------------------
    def export(self, slot: str | int, destination: Path) -> Path:
        """Copy a save to a standalone file anywhere on the player's computer."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(self.read(slot))
        return destination

    def import_file(self, source: Path, slot: str | int) -> Path:
        """Bring an exported save back into a manual slot.

        The file is decoded first so an unreadable one is refused before it can
        overwrite a slot the player still wants.
        """
        raw = Path(source).read_bytes()
        decode(raw)
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(slot)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(raw)
        os.replace(temporary, path)
        return path
