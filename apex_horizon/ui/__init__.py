"""User interface layer.

Design Bible V15.5 keeps the interface a presentation layer: gameplay systems do
not depend on interface code, and interface code contains no business logic. The
complete User Interface System is defined in V14 and V27.
"""

from .app import GameApp, run_game

__all__ = ["GameApp", "run_game"]
