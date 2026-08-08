"""The Save System — Design Bible Volume 16.

Protects the thing a long-term player values most: the time invested in a
company that may span hundreds of in-game years (V16.26). Saves are validated
before loading, repaired where possible, migrated across versions, and written
atomically so an interruption can never destroy an existing save.
"""

from .format import (
    SAVE_FORMAT_VERSION,
    SaveDocument,
    SaveFormatError,
    SaveMetadata,
    SaveSummary,
    decode,
    encode,
)
from .service import SaveResult, SaveService
from .slots import AUTOSAVE_SLOT, SaveStore, SlotInfo
from .validation import (
    LoadOutcome,
    ValidationResult,
    migrate,
    read_save,
    register_migration,
    repair,
    validate,
)

__all__ = [
    "AUTOSAVE_SLOT",
    "SAVE_FORMAT_VERSION",
    "LoadOutcome",
    "SaveDocument",
    "SaveFormatError",
    "SaveMetadata",
    "SaveResult",
    "SaveService",
    "SaveStore",
    "SaveSummary",
    "SlotInfo",
    "ValidationResult",
    "decode",
    "encode",
    "migrate",
    "read_save",
    "register_migration",
    "repair",
    "validate",
]
