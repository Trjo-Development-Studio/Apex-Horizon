"""Analytics: reading the game back to the player.

V9 requires analytics across the company, its employees, the market,
investments and time — and V9.22 requires that analysis be kept separate from
the simulation. Everything in this package reads; nothing here decides.
"""

from .history import HistoryRecorder, Snapshot
from .reports import AnalyticsService, AnalyticsTier, Metric, Report

__all__ = [
    "AnalyticsService",
    "AnalyticsTier",
    "HistoryRecorder",
    "Metric",
    "Report",
    "Snapshot",
]
