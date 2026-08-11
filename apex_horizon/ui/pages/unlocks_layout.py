"""Where every node of the Unlock Tree sits, and how large it is drawn.

Split out of the page (2026-08-10) to keep each file within the size the
project works to. These numbers belong together in one module because the
"no crossing lines" guarantee is a property of them as a set: every branch's
row and column come from LAYOUT, and every dimension scales by one factor, so
nothing outside this file can move a node onto another's row.

The nodes are deliberately compact (2026-08-11). The page shows every branch
at once inside a fixed viewport and scrolls only sideways, so the whole tree
has to fit the window's height with no vertical scrolling at all — which puts
a hard ceiling on ``ROW_STEP`` times the number of rows.
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

#: One node, and the grid it sits on, in design units at scale 1.0.
NODE_WIDTH = 150
NODE_HEIGHT = 54
COLUMN_STEP = 176
ROW_STEP = 68
#: Room left around the tree inside the viewport.
MAP_PADDING_X = 16
MAP_PADDING_Y = 12
#: How far one press of an arrow key scrolls.
PAN_STEP = 80

#: A fixed strip on the left holding branch names, which never scrolls — it
#: is chrome, not part of the map.
GUTTER_WIDTH = 96
#: A fixed strip on the right showing whatever node is selected.
INFO_PANEL_WIDTH = 240
#: The horizontal scrollbar under the map.
SCROLLBAR_HEIGHT = 12
SCROLLBAR_GAP = 6

#: The tree is drawn at whatever scale fits every branch into the height
#: available, never larger than 1.0 (bigger reads as bloated rather than
#: clearer) and never smaller than this (below it the text stops being
#: legible, which V6.10 rules out).
MIN_SCALE = 0.62
MAX_SCALE = 1.0

#: Movement, in pixels, below which a mouse-down/up is a click rather than a
#: drag — a real drag rarely holds perfectly still, and a real click rarely
#: drifts this far.
CLICK_TOLERANCE = 6

#: Row for each branch, and the column its first node sits in.
#:
#: One horizontal spine runs through the middle — Basic Investing, Create
#: Company, the Company Levels and Investment Funds (V6.5, V6.8) — with the
#: branches fanning symmetrically above and below it (V6.6, V6.7). Analytics
#: and News sit outermost because they come straight off Basic Investing; the
#: four branches that come off Create Company sit nearest the spine.
#:
#: Every branch that starts at Create Company starts in column 2, one past it,
#: so the layout says exactly what the prerequisite graph says. It is derived
#: from the graph rather than from the legacy roadmap picture: where the two
#: disagree, the graph wins (project manager, 2026-08-11).
LAYOUT: dict[str, tuple[int, int]] = {
    ANALYTICS_BRANCH: (-3, 1),
    FINANCE_BRANCH: (-2, 2),
    EMPLOYEE_BRANCH: (-1, 2),
    PRIMARY: (0, 0),
    COMPANY_BRANCH: (0, 2),
    FINAL: (0, 7),
    TRAINING_BRANCH: (1, 2),
    RECRUITMENT_BRANCH: (2, 2),
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


def position_of(unlock) -> tuple[int, int]:
    """Grid position (row, column) for one unlock, from its branch."""
    row, first_column = LAYOUT.get(unlock.branch, (0, 0))
    return row, first_column + unlock.position


def grid_bounds(unlocks) -> tuple[int, int, int]:
    """(first row, last row, last column) actually occupied by these unlocks.

    Measured from the unlocks themselves rather than from LAYOUT, so adding a
    node to the end of a branch extends the tree — and with it the scrollable
    width — without anything here needing to be told about it.
    """
    positions = [position_of(unlock) for unlock in unlocks]
    if not positions:
        return 0, 0, 0
    rows = [row for row, _ in positions]
    return min(rows), max(rows), max(column for _, column in positions)


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
