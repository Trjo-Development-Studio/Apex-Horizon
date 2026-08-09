"""Developer commands typed into the terminal that launched the game.

V15.18 names the terminal as a debugging interface, and it remains the one that
works when the window itself is the problem. The commands live in
:mod:`.commands`; this module is only the plumbing that reads lines from a
terminal and prints what they return, so the terminal and the in-game console
(Ctrl+T) always understand exactly the same language.

Reading a line from a terminal blocks until someone presses return, which would
freeze the simulation, so a daemon thread does the reading and puts whole lines
on a queue. The application drains that queue once a frame and runs the commands
on its own thread — so a command never mutates the world underneath a frame that
is halfway through drawing it.

The console is inert wherever there is no terminal to read: tests, CI, and a
windowed launch with no console all leave stdin unusable, and it simply does not
start. It is a development tool and says so on the first line it prints.
"""

from __future__ import annotations

import queue
import sys
import threading

from ..engine.logging_setup import get_logger
from .commands import Command, DeveloperCommands

logger = get_logger(__name__)

__all__ = ["Command", "DebugConsole"]


class DebugConsole:
    """Reads developer commands from the launching terminal (V15.18)."""

    def __init__(self, context=None, app=None, *, commands: DeveloperCommands | None = None):
        self.commands_source = commands or DeveloperCommands(context, app=app)
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._running = False
        self._printing = False

    # -- what the commands act on ------------------------------------------
    @property
    def context(self):
        return self.commands_source.context

    @context.setter
    def context(self, value) -> None:
        self.commands_source.context = value

    @property
    def commands(self) -> dict[str, Command]:
        """The command table, shared with every other console."""
        return self.commands_source.commands

    # -- lifecycle ---------------------------------------------------------
    @property
    def available(self) -> bool:
        """Whether there is a terminal to read commands from."""
        try:
            return bool(sys.stdin) and sys.stdin.isatty()
        except (AttributeError, ValueError):
            return False

    def start(self) -> bool:
        """Begin reading, if a terminal is attached. Safe to call always."""
        if self._running or not self.available:
            return False
        self._running = True
        self._printing = True
        self.commands_source.on_output.append(self._print)
        self._thread = threading.Thread(target=self._read_lines, daemon=True,
                                        name="apex-debug-console")
        self._thread.start()
        print("Apex Horizon developer console (V15.18). Type 'help' for commands.",
              flush=True)
        return True

    def stop(self) -> None:
        self._running = False
        if self._printing:
            self._printing = False
            if self._print in self.commands_source.on_output:
                self.commands_source.on_output.remove(self._print)

    def _print(self, message: str) -> None:
        print(message, flush=True)

    def _read_lines(self) -> None:
        """Block on the terminal, off the main thread."""
        while self._running:
            try:
                line = sys.stdin.readline()
            except (OSError, ValueError):
                break
            if not line:
                break
            self._queue.put(line.strip())

    # -- running -----------------------------------------------------------
    def poll(self) -> None:
        """Run whatever has been typed. Called once a frame by the app."""
        while True:
            try:
                line = self._queue.get_nowait()
            except queue.Empty:
                return
            if line:
                print(self.execute(line), flush=True)

    def execute(self, line: str) -> str:
        """Run one command line and return what to print."""
        return self.commands_source.execute(line)
