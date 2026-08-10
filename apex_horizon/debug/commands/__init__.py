"""Developer commands, and what they do to the running game.

V15.18 asks for a developer console covering money, time, employees, research,
market events and the economy. This module is the commands themselves, with no
opinion about where they were typed: the terminal reader in :mod:`.console` and
the in-game overlay in :mod:`..ui.console` both drive this one object, so there
is a single definition of what every command means and a single help text
describing it.

Two rules shape everything here.

**Commands act on the real systems.** ``money player add 1000`` moves the same
cash the market spends, the interface draws and the save writes; ``time add
1year`` runs the simulation through every one of those days rather than moving a
label. Where a legitimate game API exists it is used (V15.28) — company money
arrives as owner capital through the company's own transfer method, so the
ledger and cash-flow statement stay truthful. What a command deliberately skips
is the *price*: that is the point of a debug tool.

**Nothing typed can end the game.** Every command validates its own arguments
and returns a sentence; the caller only prints it.

Time is the exception to running immediately. A year takes several seconds to
simulate honestly, so ``time add 5year`` would freeze the window for half a
minute if it ran inside one command. Instead the command schedules the days and
:meth:`DeveloperCommands.pump` advances them a slice at a time, once per frame,
leaving the game drawing and responsive while the world catches up.

The commands are split across sibling modules by what they act on; this
package re-exports the names the rest of the game uses, so
``from apex_horizon.debug.commands import DeveloperCommands`` reads as it did
when they all shared one file (split 2026-08-10, for file size).
"""

from .base import Command, Reply, no
from .core import DeveloperCommands

__all__ = ["Command", "DeveloperCommands", "Reply", "no"]
