"""Save validation, recovery, and migration.

Design Bible V16.13 requires every save to be validated before loading — file
integrity, required data, format, version, data types — and is explicit that an
invalid save must never silently load. V16.14 then defines what to do when one
is broken: attempt automatic repair, load the repaired save if that succeeds,
and otherwise ask the player whether they still wish to try.

V16.15 covers the other reason a save may not load cleanly: it was written by an
older version. Migration is attempted automatically, and the player is told if
it fails. Between them these rules protect the thing a long-term player values
most — the time already invested (V16.26).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ..logging_setup import get_logger
from .format import SAVE_FORMAT_VERSION, SaveDocument, SaveFormatError, decode

logger = get_logger(__name__)

# Every top-level system whose state a save is expected to carry (V16.11).
REQUIRED_STATE_KEYS = ("engine", "world", "market", "economy", "player")


@dataclass
class ValidationResult:
    """The outcome of checking a save before loading it."""

    valid: bool
    problems: list[str] = field(default_factory=list)
    repaired: bool = False

    def describe(self) -> str:
        if self.valid and not self.problems:
            return "Save is valid."
        return "; ".join(self.problems)


def validate(document: SaveDocument) -> ValidationResult:
    """Check a decoded save for the things V16.13 requires."""
    problems: list[str] = []

    metadata = document.metadata
    if not metadata.save_id:
        problems.append("the save has no identifier")
    if not isinstance(metadata.save_format_version, int):
        problems.append("the save format version is not a number")
    elif metadata.save_format_version > SAVE_FORMAT_VERSION:
        problems.append(
            f"it was written by a newer version of the game "
            f"(format {metadata.save_format_version})"
        )

    if not isinstance(document.state, dict):
        problems.append("the saved state is not readable")
        return ValidationResult(valid=False, problems=problems)

    missing = [key for key in REQUIRED_STATE_KEYS if key not in document.state]
    if missing:
        problems.append(f"missing data for: {', '.join(missing)}")

    for key in REQUIRED_STATE_KEYS:
        value = document.state.get(key)
        if value is not None and not isinstance(value, dict):
            problems.append(f"the {key} data is the wrong type")

    return ValidationResult(valid=not problems, problems=problems)


def repair(document: SaveDocument) -> tuple[SaveDocument, list[str]]:
    """Attempt to make a damaged save loadable (V16.14).

    Repair is deliberately conservative: it fills in what can be reconstructed
    safely and reports what it did, rather than inventing gameplay data. A save
    that cannot be repaired honestly is better refused than silently altered.
    """
    notes: list[str] = []

    if not document.metadata.save_id:
        from ..values import new_save_id

        document.metadata.save_id = new_save_id()
        notes.append("assigned a new save identifier")

    if not isinstance(document.metadata.save_format_version, int):
        document.metadata.save_format_version = SAVE_FORMAT_VERSION
        notes.append("assumed the current save format version")

    if not isinstance(document.state, dict):
        document.state = {}
        notes.append("reset unreadable state")

    for key in REQUIRED_STATE_KEYS:
        value = document.state.get(key)
        if value is not None and not isinstance(value, dict):
            document.state.pop(key)
            notes.append(f"discarded unreadable {key} data")

    return document, notes


# -- migration (V16.15) ----------------------------------------------------

# Upgrades from one save format version to the next. Adding an entry is all it
# takes to keep older saves loading, which is what V19.17 asks for whenever a
# development change would otherwise break compatibility.
Migration = Callable[[SaveDocument], SaveDocument]
MIGRATIONS: dict[int, Migration] = {}


def register_migration(from_version: int) -> Callable[[Migration], Migration]:
    """Register the upgrade that takes a save from ``from_version`` to the next."""

    def decorator(function: Migration) -> Migration:
        MIGRATIONS[from_version] = function
        return function

    return decorator


def migrate(document: SaveDocument) -> tuple[SaveDocument, list[str]]:
    """Bring an older save up to the current format (V16.15)."""
    notes: list[str] = []
    version = document.metadata.save_format_version
    while version < SAVE_FORMAT_VERSION:
        migration = MIGRATIONS.get(version)
        if migration is None:
            raise SaveFormatError(
                f"This save uses format {version}, which cannot be upgraded automatically."
            )
        document = migration(document)
        version += 1
        document.metadata.save_format_version = version
        notes.append(f"upgraded save format {version - 1} to {version}")
        logger.info("Migrated save from format %d to %d.", version - 1, version)
    return document, notes


@dataclass
class LoadOutcome:
    """Everything the game learned while trying to load a save."""

    document: SaveDocument | None
    ok: bool
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    needs_confirmation: bool = False

    def describe(self) -> str:
        if self.ok and not self.notes:
            return "Loaded."
        parts = self.notes + self.problems
        return "; ".join(parts) if parts else "Loaded."


def read_save(raw: bytes, *, allow_damaged: bool = False) -> LoadOutcome:
    """Decode, migrate, validate and if necessary repair a save.

    Returns an outcome rather than raising, so the caller can put the choice to
    the player exactly as V16.14 describes: if automatic repair does not
    succeed, they are asked whether to attempt the load anyway.
    """
    notes: list[str] = []
    try:
        document = decode(raw)
    except SaveFormatError as exc:
        # The checksum or framing failed. Try to salvage the contents before
        # giving up, then let the player decide (V16.14).
        try:
            document = decode(raw, verify=False)
        except SaveFormatError:
            return LoadOutcome(None, ok=False, problems=[str(exc)])
        notes.append("the file is damaged but its contents could be read")
        if not allow_damaged:
            return LoadOutcome(
                document, ok=False, problems=[str(exc)], notes=notes,
                needs_confirmation=True,
            )

    try:
        document, migration_notes = migrate(document)
        notes.extend(migration_notes)
    except SaveFormatError as exc:
        return LoadOutcome(document, ok=False, problems=[str(exc)], notes=notes)

    result = validate(document)
    if not result.valid:
        document, repair_notes = repair(document)
        notes.extend(repair_notes)
        result = validate(document)
        if not result.valid:
            return LoadOutcome(
                document, ok=False, problems=result.problems, notes=notes,
                needs_confirmation=allow_damaged is False,
            )
        notes.append("repaired automatically")

    return LoadOutcome(document, ok=True, notes=notes)
