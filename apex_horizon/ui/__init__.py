"""User interface layer.

Design Bible V15.5 requires the interface to remain a presentation layer:
gameplay systems must not depend on interface code, and interface code must not
contain business logic. The full User Interface System (V14, V27) is built in a
later milestone; this layer currently provides only the application shell.
"""

from .window import GameWindow, run_game

__all__ = ["GameWindow", "run_game"]
