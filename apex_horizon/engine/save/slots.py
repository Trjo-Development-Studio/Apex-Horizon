"""Save slots on disk.

Design Bible V16.8 gives the player five manual slots, each an entirely separate
world (V16.12). V16.9 lists what a slot must show without loading it, which is
why every file carries its own summary.

V16.7 additionally described a *separate* rolling autosave file. The project
manager removed it (2026-08-09): a save game is bound to one slot for its whole
life, and autosaving writes to that slot rather than to a sixth entry that shows
up in the menu looking like a different game. The autosave name survives only so
a save directory written by an earlier build is still readable.

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

#: The file older builds wrote rolling autosaves to. Nothing writes it now.
AUTOSAVE_SLOT = "autosave"
SAVE_SUFFIX = ".ahsave"


def _format_playtime(seconds: float) -> str:
    """Total time played in this save, in whichever unit reads naturally."""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes}m played"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m played"
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h played"


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
        """True only for a leftover file from a build that kept one."""
        return self.slot == AUTOSAVE_SLOT

    @property
    def label(self) -> str:
        if self.is_autosave:
            return "Autosave"
        return f"Slot {self.slot}"

    @property
    def title(self) -> str:
        """What to call this save in a list: its name, or the empty slot."""
        if self.exists and not self.damaged and self.metadata is not None:
            return self.metadata.name
        return self.label

    def describe(self) -> str:
        """A save slot's name, money, net worth, date and playtime, in the
        order the project manager specified (V16.9, QoL pass 2026-08-10).
        All figures were already computed for the summary/metadata; this
        only formats what is already there. Truncated by whatever draws it
        on a narrow window, the same as every other row of text in the
        interface, rather than a second layout system of its own.
        """
        if not self.exists:
            return "Empty"
        if self.damaged or self.summary is None or self.metadata is None:
            return "Damaged save"
        return (
            f"{self.metadata.name} · "
            f"{self.summary.money_value.format(decimals=0)} cash · "
            f"{self.summary.net_worth_value.format(decimals=0)} net worth · "
            f"{self.summary.date_label()} · "
            f"{_format_playtime(self.metadata.playtime_seconds)}"
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
        """The slots a player can use. There is no separate autosave slot."""
        return [str(index) for index in range(1, self.manual_slots + 1)]

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
        """Write a save atomically, so an interruption cannot destroy the old one.

        The temporary file carries the writing process's id. A fixed name looks
        atomic but is not: two games sharing a save directory would write the
        same temporary path, and the first to finish would move the file out
        from under the second, which then fails with the old save already gone.
        A per-process name keeps each write independent, so the replace either
        happens completely or not at all.
        """
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(slot)
        temporary = path.with_suffix(f"{path.suffix}.{os.getpid()}.tmp")
        payload = encode(document)
        try:
            with open(temporary, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            # Never leave a stray temporary behind for a save that failed.
            temporary.unlink(missing_ok=True)
            raise
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
