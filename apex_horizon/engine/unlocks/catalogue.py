"""The Unlock Tree's contents.

Every node, edge and branch here comes from Design Bible Volume 6: the primary
progression of V6.5, the two Basic Investing branches of V6.6, the five Company
Level 2 branches of V6.7, and the converging final unlock of V6.8. Nothing is
invented — where the Bible names an unlock, it appears; where it does not, none
was added.

Prices are never written here. Each unlock declares how deep it sits, and the
price comes from a multiple of the company founding cost held in configuration
(V15.10, and the project manager's ruling that unlock prices stay tunable). One
number in `config/gameplay.toml` therefore rescales the whole tree.
"""

from __future__ import annotations

from .tree import Unlock

# -- primary progression (V6.5) -------------------------------------------
BASIC_INVESTING = "basic_investing"
CREATE_COMPANY = "create_company"
COMPANY_LEVEL_2 = "company_level_2"

# -- Analytics branch (V6.6.1, V9.6) --------------------------------------
BASIC_ANALYTICS = "basic_analytics"
BETTER_ANALYTICS_1 = "better_analytics_1"
BETTER_ANALYTICS_2 = "better_analytics_2"
BETTER_ANALYTICS_3 = "better_analytics_3"

# -- News branch (V6.6.2, V10.4) ------------------------------------------
BASIC_NEWS = "basic_news"
MARKET_NEWS = "market_news"
ECONOMIC_NEWS = "economic_news"
BREAKING_NEWS = "breaking_news"

# -- Finance branch (V6.7.1, V17) -----------------------------------------
FINANCE = "finance"
BETTER_FINANCE_1 = "better_finance_1"
BETTER_FINANCE_2 = "better_finance_2"
BETTER_FINANCE_3 = "better_finance_3"

# -- Employee branch (V6.7.2, V5) -----------------------------------------
EMPLOYEES = "employees"
BETTER_EMPLOYEES_1 = "better_employees_1"
BETTER_EMPLOYEES_2 = "better_employees_2"
BETTER_EMPLOYEES_3 = "better_employees_3"

# -- Company branch (V6.7.3, V3.7, V9.9) ----------------------------------
COMPANY_LEVEL_3 = "company_level_3"
COMPANY_LEVEL_4 = "company_level_4"
COMPANY_LEVEL_5 = "company_level_5"
COMPANY_ANALYTICS = "company_analytics"

# -- Employee Training branch (V6.7.4, V5.9) ------------------------------
EMPLOYEE_TRAINING = "employee_training"
BETTER_TRAINING_1 = "better_training_1"
BETTER_TRAINING_2 = "better_training_2"
BETTER_TRAINING_3 = "better_training_3"

# -- Recruitment branch (V6.7.5, V18) -------------------------------------
BETTER_RECRUITMENT = "better_recruitment"
MORE_APPLICANTS = "more_applicants"
EMPLOYEE_STRENGTHS = "employee_strengths"
EMPLOYEE_PERFORMANCE = "employee_performance"

# -- the final unlock (V6.8) ----------------------------------------------
INVESTMENT_FUNDS = "investment_funds"

#: Branch identifiers, used only for laying the tree out (V6.10).
PRIMARY = "primary"
ANALYTICS_BRANCH = "analytics"
NEWS_BRANCH = "news"
FINANCE_BRANCH = "finance"
EMPLOYEE_BRANCH = "employees"
COMPANY_BRANCH = "company"
TRAINING_BRANCH = "training"
RECRUITMENT_BRANCH = "recruitment"
FINAL = "final"


UNLOCKS: tuple[Unlock, ...] = (
    # -- primary (V6.5) ---------------------------------------------------
    Unlock(
        key=BASIC_INVESTING, name="Basic Investing", branch=PRIMARY, position=0,
        description="Trade shares with your own money. Every player starts with this.",
        owned_at_start=True,
    ),
    Unlock(
        key=CREATE_COMPANY, name="Create Company", branch=PRIMARY, position=1,
        description="Permission to found a company. Founding it costs extra.",
        requires=(BASIC_INVESTING,), cost_tier=0,
    ),
    Unlock(
        key=COMPANY_LEVEL_2, name="Company Level 2", branch=PRIMARY, position=2,
        description="Grow the company, raising how many people it can employ.",
        requires=(CREATE_COMPANY,), cost_tier=1,
    ),

    # -- Analytics branch (V6.6.1) ----------------------------------------
    Unlock(
        key=BASIC_ANALYTICS, name="Basic Analytics", branch=ANALYTICS_BRANCH, position=0,
        description="Open the Analytics page: how your position actually stands.",
        requires=(BASIC_INVESTING,), cost_tier=0,
    ),
    Unlock(
        key=BETTER_ANALYTICS_1, name="Better Analytics 1", branch=ANALYTICS_BRANCH, position=1,
        description="Adds margins, net worth and change over time.",
        requires=(BASIC_ANALYTICS,), cost_tier=1,
    ),
    Unlock(
        key=BETTER_ANALYTICS_2, name="Better Analytics 2", branch=ANALYTICS_BRANCH, position=2,
        description="Adds lifetime results, morale and industry standings.",
        requires=(BETTER_ANALYTICS_1,), cost_tier=2,
    ),
    Unlock(
        key=BETTER_ANALYTICS_3, name="Better Analytics 3", branch=ANALYTICS_BRANCH, position=3,
        description="Adds employee and market analytics in full.",
        requires=(BETTER_ANALYTICS_2,), cost_tier=3,
    ),

    # -- News branch (V6.6.2) ---------------------------------------------
    Unlock(
        key=BASIC_NEWS, name="Basic News", branch=NEWS_BRANCH, position=0,
        description="Read the financial press: company stories as they happen.",
        requires=(BASIC_INVESTING,), cost_tier=0,
    ),
    Unlock(
        key=MARKET_NEWS, name="Market News", branch=NEWS_BRANCH, position=1,
        description="Weekly market reports: which industries lead and lag.",
        requires=(BASIC_NEWS,), cost_tier=1,
    ),
    Unlock(
        key=ECONOMIC_NEWS, name="Economic News", branch=NEWS_BRANCH, position=2,
        description="Reporting on the economy as it turns.",
        requires=(MARKET_NEWS,), cost_tier=2,
    ),
    Unlock(
        key=BREAKING_NEWS, name="Breaking News", branch=NEWS_BRANCH, position=3,
        description="The extraordinary sessions others do not get to see.",
        requires=(ECONOMIC_NEWS,), cost_tier=3,
    ),

    # -- Finance branch (V6.7.1) ------------------------------------------
    Unlock(
        key=FINANCE, name="Finance", branch=FINANCE_BRANCH, position=0,
        description="Borrow from the banks to invest beyond your own capital.",
        requires=(COMPANY_LEVEL_2,), cost_tier=2,
    ),
    Unlock(
        key=BETTER_FINANCE_1, name="Better Finance 1", branch=FINANCE_BRANCH, position=1,
        description="Banks lend more, and more cheaply.",
        requires=(FINANCE,), cost_tier=3,
    ),
    Unlock(
        key=BETTER_FINANCE_2, name="Better Finance 2", branch=FINANCE_BRANCH, position=2,
        description="Better terms again as your standing improves.",
        requires=(BETTER_FINANCE_1,), cost_tier=4,
    ),
    Unlock(
        key=BETTER_FINANCE_3, name="Better Finance 3", branch=FINANCE_BRANCH, position=3,
        description="The strongest lending terms available.",
        requires=(BETTER_FINANCE_2,), cost_tier=5,
    ),

    # -- Employee branch (V6.7.2) -----------------------------------------
    Unlock(
        key=EMPLOYEES, name="Employees", branch=EMPLOYEE_BRANCH, position=0,
        description="Opens the employee quality levels below.",
        requires=(COMPANY_LEVEL_2,), cost_tier=2,
    ),
    Unlock(
        key=BETTER_EMPLOYEES_1, name="Better Employees 1", branch=EMPLOYEE_BRANCH, position=1,
        description="Applicants arrive with skills up to 20.",
        requires=(EMPLOYEES,), cost_tier=3,
    ),
    Unlock(
        key=BETTER_EMPLOYEES_2, name="Better Employees 2", branch=EMPLOYEE_BRANCH, position=2,
        description="Applicants arrive with skills up to 30.",
        requires=(BETTER_EMPLOYEES_1,), cost_tier=4,
    ),
    Unlock(
        key=BETTER_EMPLOYEES_3, name="Better Employees 3", branch=EMPLOYEE_BRANCH, position=3,
        description="Applicants arrive with skills up to 40.",
        requires=(BETTER_EMPLOYEES_2,), cost_tier=5,
    ),

    # -- Company branch (V6.7.3) ------------------------------------------
    Unlock(
        key=COMPANY_LEVEL_3, name="Company Level 3", branch=COMPANY_BRANCH, position=1,
        description="A larger organisation, and room for more people.",
        requires=(COMPANY_LEVEL_2,), cost_tier=3,
    ),
    Unlock(
        key=COMPANY_LEVEL_4, name="Company Level 4", branch=COMPANY_BRANCH, position=2,
        description="A larger organisation again.",
        requires=(COMPANY_LEVEL_3,), cost_tier=4,
    ),
    Unlock(
        key=COMPANY_LEVEL_5, name="Company Level 5", branch=COMPANY_BRANCH, position=3,
        description="The largest company the game supports.",
        requires=(COMPANY_LEVEL_4,), cost_tier=5,
    ),
    Unlock(
        key=COMPANY_ANALYTICS, name="Company Analytics", branch=COMPANY_BRANCH, position=4,
        description="Department performance and operational efficiency in full.",
        requires=(COMPANY_LEVEL_5,), cost_tier=6,
    ),

    # -- Employee Training branch (V6.7.4) --------------------------------
    Unlock(
        key=EMPLOYEE_TRAINING, name="Employee Training", branch=TRAINING_BRANCH, position=0,
        description="Send employees on training to raise their skills.",
        requires=(COMPANY_LEVEL_2,), cost_tier=2,
    ),
    Unlock(
        key=BETTER_TRAINING_1, name="Better Training 1", branch=TRAINING_BRANCH, position=1,
        description="Training teaches faster.",
        requires=(EMPLOYEE_TRAINING,), cost_tier=3,
    ),
    Unlock(
        key=BETTER_TRAINING_2, name="Better Training 2", branch=TRAINING_BRANCH, position=2,
        description="Training teaches faster again.",
        requires=(BETTER_TRAINING_1,), cost_tier=4,
    ),
    Unlock(
        key=BETTER_TRAINING_3, name="Better Training 3", branch=TRAINING_BRANCH, position=3,
        description="The most effective training available.",
        requires=(BETTER_TRAINING_2,), cost_tier=5,
    ),

    # -- Recruitment branch (V6.7.5) --------------------------------------
    Unlock(
        key=BETTER_RECRUITMENT, name="Better Recruitment", branch=RECRUITMENT_BRANCH, position=0,
        description="Your reputation counts for more when candidates apply.",
        requires=(COMPANY_LEVEL_2,), cost_tier=2,
    ),
    Unlock(
        key=MORE_APPLICANTS, name="More Applicants", branch=RECRUITMENT_BRANCH, position=1,
        description="A larger pool of candidates to choose between.",
        requires=(BETTER_RECRUITMENT,), cost_tier=3,
    ),
    Unlock(
        key=EMPLOYEE_STRENGTHS, name="Employee Strengths", branch=RECRUITMENT_BRANCH, position=2,
        description="See the hidden characteristics behind how people work.",
        requires=(MORE_APPLICANTS,), cost_tier=4,
    ),
    Unlock(
        key=EMPLOYEE_PERFORMANCE, name="Employee Performance", branch=RECRUITMENT_BRANCH,
        position=3,
        description="Performance statistics for everyone you employ.",
        requires=(EMPLOYEE_STRENGTHS,), cost_tier=5,
    ),

    # -- the final unlock (V6.8) ------------------------------------------
    Unlock(
        key=INVESTMENT_FUNDS, name="Investment Funds", branch=FINAL, position=0,
        description="Manage capital for outside investors. Every branch leads here.",
        requires=(
            BETTER_ANALYTICS_3, BETTER_FINANCE_3, BETTER_EMPLOYEES_3, COMPANY_ANALYTICS,
            BETTER_TRAINING_3, EMPLOYEE_PERFORMANCE, BREAKING_NEWS,
        ),
        cost_tier=6,
        # The Investment Funds System is Volume 11, which is not built yet. The
        # node is shown because V6.14 wants the remaining tree visible as
        # long-term ambition, but it cannot be bought: V6.3 forbids selling an
        # unlock that changes nothing.
        implemented=False,
    ),
)
