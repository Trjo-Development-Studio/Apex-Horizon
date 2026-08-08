"""The Investment System — Design Bible Volume 8.

The player builds an organisation that researches, evaluates, approves and
executes investments, rather than buying and selling personally (V8.2). Their
control is exercised upstream — hiring, department assignment, training and
investment limits — while employees perform the operational work (V8.14, V8.25).
"""

from .opportunity import Opportunity, Position, Stage
from .workflow import InvestmentSystem

__all__ = ["InvestmentSystem", "Opportunity", "Position", "Stage"]
