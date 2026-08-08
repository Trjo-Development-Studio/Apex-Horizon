"""The game's pages.

Each major screen is its own module, as V14 requires, and all of them are built
from the shared layout in :mod:`.base` so that every page behaves the same way
(V14.20, V14.28).
"""

from .analytics import AnalyticsPage
from .base import EmptyStatePage, Page
from .company import CompanyPage, FinancePage
from .dashboard import DashboardPage
from .employees import EmployeeDetailPage, EmployeesPage
from .funds import FundDetailPage, FundsPage
from .market import CompanyDetailPage, MarketPage
from .news import NewsPage
from .simple import InvestmentsPage, SettingsPage
from .subsidiaries import SubsidiariesPage, SubsidiaryDetailPage
from .unlocks import UnlockTreePage

__all__ = [
    "AnalyticsPage",
    "CompanyDetailPage",
    "CompanyPage",
    "DashboardPage",
    "EmployeeDetailPage",
    "EmployeesPage",
    "EmptyStatePage",
    "FinancePage",
    "FundDetailPage",
    "FundsPage",
    "InvestmentsPage",
    "MarketPage",
    "NewsPage",
    "Page",
    "SettingsPage",
    "SubsidiariesPage",
    "SubsidiaryDetailPage",
    "UnlockTreePage",
]
