"""The game's pages.

Each major screen is its own module, as V14 requires, and all of them are built
from the shared layout in :mod:`.base` so that every page behaves the same way
(V14.20, V14.28).
"""

from .analytics import AnalyticsPage
from .base import EmptyStatePage, Page
from .company import CompanyPage, FinancePage
from .dashboard import DashboardPage
from .employee_detail import EmployeeDetailPage
from .employees import EmployeesPage
from .funds import FundDetailPage, FundsPage
from .market import CompanyDetailPage, MarketPage
from .news import NewsPage
from .portfolio import PortfolioPage
from .simple import InvestmentsPage, SettingsPage
from .statistics import StatisticsPage
from .subsidiaries import SubsidiariesPage, SubsidiaryDetailPage
from .subsidiaries_buy import SubsidiariesBuyPage, SubsidiaryPurchaseDetailPage
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
    "PortfolioPage",
    "SettingsPage",
    "StatisticsPage",
    "SubsidiariesBuyPage",
    "SubsidiariesPage",
    "SubsidiaryDetailPage",
    "SubsidiaryPurchaseDetailPage",
    "UnlockTreePage",
]
