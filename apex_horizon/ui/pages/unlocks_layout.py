"""Where every node of the Unlock Tree sits, and how large it is drawn.

Split out of the page (2026-08-10) to keep each file within the size the
project works to. These numbers belong together in one module because the
"no crossing lines" guarantee is a property of them as a set: every branch's
row and column come from LAYOUT, and every dimension scales by one zoom
factor, so nothing outside this file can move a node onto another's row.
"""

from __future__ import annotations

from ...engine.unlocks import (
    ANALYTICS_BRANCH,
    COMPANY_BRANCH,
    EMPLOYEE_BRANCH,
    FINAL,
    FINANCE_BRANCH,
    NEWS_BRANCH,
    PRIMARY,
    RECRUITMENT_BRANCH,
    TRAINING_BRANCH,
)
from ..widgets import draw_text

NODE_WIDTH = 168
NODE_HEIGHT = 78
COLUMN_STEP = 208
ROW_STEP = 96
PAN_STEP = 60
#: A fixed strip on the left holding branch names, which never scrolls or
#: scales with zoom — it is chrome, not part of the map.
GUTTER_WIDTH = 104
#: A fixed strip on the right showing whatever node is selected.
INFO_PANEL_WIDTH = 260

#: Discrete zoom presets, applied uniformly to every dimension of the map.
ZOOM_LEVELS: tuple[float, ...] = (0.75, 1.0, 1.4)
DEFAULT_ZOOM_INDEX = 1
#: Movement, in pixels, below which a mouse-down/up is a click rather than a
#: drag — a real drag rarely holds perfectly still, and a real click rarely
#: drifts this far.
CLICK_TOLERANCE = 6

#: Row for each branch, and the column its first node sits in.
#:
#: Laid out to match the roadmap reference kept with the legacy prototype
#: (`docs/Unlock tree layout example.png` there — layout only; colours and
#: styling stay governed by Design Bible 2.0). Its organising idea is a single
#: horizontal spine straight through the middle — Basic Investing, Create
#: Company, the Company Levels, and Investment Funds where everything
#: converges (V6.5, V6.8) — with branches fanning symmetrically above and
#: below it, rather than the spine sitting near the top with every branch
#: hanging beneath. Analytics and News sit outermost because they are the two
#: that come straight off Basic Investing rather than off a company; the four
#: Company Level 2 branches sit nearest the spine they depend on.
LAYOUT: dict[str, tuple[int, int]] = {
    ANALYTICS_BRANCH: (-3, 1),
    FINANCE_BRANCH: (-2, 3),
    EMPLOYEE_BRANCH: (-1, 3),
    #: The spine: three branches sharing one row, in adjoining column ranges
    #: (0-1, 2-6, 8) so they read as one continuous line left to right.
    PRIMARY: (0, 0),
    COMPANY_BRANCH: (0, 2),
    FINAL: (0, 8),
    TRAINING_BRANCH: (1, 3),
    RECRUITMENT_BRANCH: (2, 3),
    NEWS_BRANCH: (3, 1),
}

BRANCH_LABELS = {
    ANALYTICS_BRANCH: "Analytics",
    NEWS_BRANCH: "News",
    FINANCE_BRANCH: "Finance",
    EMPLOYEE_BRANCH: "Employees",
    COMPANY_BRANCH: "Company",
    TRAINING_BRANCH: "Training",
    RECRUITMENT_BRANCH: "Recruitment",
}


def _wrap(surface, font, text, rect, colour) -> None:
    words, line, y = str(text).split(), "", rect.top
    for word in words:
        candidate = f"{line} {word}".strip()
        if font.size(candidate)[0] <= rect.width or not line:
            line = candidate
            continue
        draw_text(surface, font, line, (rect.left, y), colour)
        y += font.get_height() + 3
        line = word
    if line:
        draw_text(surface, font, line, (rect.left, y), colour)
