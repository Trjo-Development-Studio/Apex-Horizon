# Save System

Implements Design Bible Volume 16. Code lives in `apex_horizon/engine/save/`.

The Save System protects the thing a long-term player values most: the time
invested in a company that may span hundreds of in-game years (V16.26).

## The file format (V16.18–V16.20)

```
APEXSAVE | container version | 4-byte checksum | obfuscated gzip of JSON
```

Structured JSON internally, compressed on the way to disk — small files, and
not casually editable. A light obfuscation pass sits alongside the compression
(V16.19). **None of this is security, and it is not presented as such**: the aim
is only to discourage accidental modification.

The checksum is what lets validation detect a damaged file *before* anything
tries to interpret it.

## Saving is atomic

Saves are written to a temporary file, flushed, and then moved into place. An
interruption mid-write therefore cannot destroy the save that already existed —
V16.30's corrupted-mid-write case costs at most the new save, never the old one.
A test asserts the previous save survives a failed write.

## Slots (V16.7–V16.10)

Five manual slots, each an entirely separate world (V16.12), plus **one rolling
autosave** that each new autosave replaces. Every file carries its own summary —
name, money, net worth, date, playtime — so a slot can be listed without loading
its world (V16.9).

A slot that cannot be summarised is shown as **damaged** rather than hidden: the
player should know it is there.

All saves live in one flat directory with stable names, which is what allows the
Steam Cloud support of V16.23 to be added later without redesign.

## Loading: validate, migrate, repair (V16.13–V16.15)

An invalid save never silently loads. Loading runs in order:

1. **Decode.** If the checksum fails, the contents are still salvaged if
   possible, and the player is asked whether to try anyway (V16.14). If the
   compressed body itself is destroyed, that is reported rather than guessed at.
2. **Migrate.** Older formats are upgraded through a registry of migrations;
   adding one entry keeps older saves loading, which is what V19.17 requires
   whenever a change would otherwise break compatibility.
3. **Validate.** File integrity, required systems, format version, and types.
4. **Repair.** Conservative: it fills in what can be reconstructed safely and
   reports what it did, rather than inventing gameplay data. A save that cannot
   be repaired honestly is refused rather than silently altered.

```python
outcome = service.load_from_slot(1)
if outcome.needs_confirmation:
    ...  # ask the player, then load_from_slot(1, allow_damaged=True)
```

## What is saved (V16.11)

Engine (including the random generator's state), world, market with every
listing's **full price history** (V4.22), economy, banking, and the player with
their company, ledger and loans. Also the **generation state** — the identifier
allocator and the used-name sets — so companies created after a reload never
collide with the ones generated before it.

Temporary interface state is deliberately not saved.

## Autosaving (V16.5–V16.7, V16.24)

- Every ten **real** minutes of play by default, adjustable in Settings, and
  switchable off (`save.autosave_interval_minutes`). V16.5 says every in-game
  month; a month lasts twenty-eight seconds at normal speed, so the project
  manager set a real-time interval instead — see
  [design decisions](design-decisions.md). Time spent on an open decision does
  not count toward it.
- Immediately **before** a major irreversible decision (V16.6), so the moment
  before it is always available.
- One rolling autosave; each replaces the last.
- A brief "Autosaved" notification that never pauses the game.

## Save & Exit (V16.3, V16.4)

There is no standalone Save button. Save & Exit pauses the simulation, attempts
the save, and leaves **only if it succeeds** — a failed save returns the player
to the running game with an error so another attempt can be made, rather than
losing the session.

## Export and import (V16.21, V16.22)

A slot can be exported to a standalone file anywhere, and an exported file
imported back into any manual slot. An import decodes the file first, so an
unreadable one is refused *before* it can overwrite a slot the player still
wants.

## Determinism across a reload

Because the engine saves its generator state alongside the seed, a reloaded
world continues the same random sequence rather than restarting it. A test saves
a game, plays thirty days, reloads, replays the same thirty days, and asserts
every share price matches (V15.11, V16.28).
