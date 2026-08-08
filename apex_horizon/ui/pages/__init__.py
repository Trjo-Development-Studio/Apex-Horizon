"""The game's pages.

Each major screen is its own module, as V14 requires, and all of them are built
from the shared layout in :mod:`.base` so that every page behaves the same way
(V14.20, V14.28).
"""

from .base import EmptyStatePage, Page
from .company import CompanyPage, FinancePage
from .dashboard import DashboardPage
from .market import CompanyDetailPage, MarketPage
from .simple import InvestmentsPage, NewsPage, SettingsPage, UnlockTreePage

__all__ = [
    "CompanyDetailPage",
    "CompanyPage",
    "DashboardPage",
    "EmptyStatePage",
    "FinancePage",
    "InvestmentsPage",
    "MarketPage",
    "NewsPage",
    "Page",
    "SettingsPage",
    "UnlockTreePage",
]
