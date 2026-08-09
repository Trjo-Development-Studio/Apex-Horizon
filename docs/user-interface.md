# User Interface

Implements Design Bible Volumes 14 and 27. Code lives in `apex_horizon/ui/`.

The interface is a **presentation layer** (V15.5): it reads game state and asks
systems to do things, but holds no gameplay logic, and no system knows it exists.
Pages see the simulation only through `GameContext`.

## Visual language (V1.15, V14.3)

A near-monochrome dark palette drawn from professional financial software.
Colour carries meaning rather than decoration: one accent for the active
element, and green/red reserved strictly for financial gain and loss. Everything
visual comes from `theme.py` — a page that invents its own colour or spacing
would break the consistency V27.11 depends on.

## Icons (V1.15, V27.10)

Monochrome outline icons, **drawn rather than loaded**. Simple geometry keeps
every icon in the same weight and palette, which is what makes the set read as
one family, and means no icon can go missing at runtime.

Every icon is paired with a label or tooltip: navigation must never depend on
icon recognition alone.

## Layout

```
┌──┬────────────────────────────────────────────┐
│  │ date · economy        save · ×1 ×2 ×3      │  top bar
│  ├────────────────────────────────────────────┤
│ s│ Header                                     │
│ i│ Breadcrumb                                 │
│ d│ ┌────┐ ┌────┐ ┌────┐ ┌────┐   summary cards│
│ e│ Search                                     │
│ b│ Main content                               │
│ a│                                            │
│ r│  ┌──────────┐  notifications, lower-right   │
└──┴────────────────────────────────────────────┘
```

Every page follows the order V14.20 mandates — header, breadcrumb, summary
cards, search, main content — and the base `Page` class decides where those
parts go rather than each page positioning itself (V14.28). That is what makes
opening the fiftieth page feel exactly like opening the first (V14.25).

## The Start Menu

The first screen, and where Save & Exit returns to (V16.4). It is deliberately
not another dashboard: a title, four actions, and the version.

Behind it is a drawn backdrop (`ui/background.py`) — a dark base with a slow
gradient, one off-centre light, and a few very faint overlapping shapes and
lines. It is deliberately abstract: the project manager ruled out anything
representational, and ruled out a regular grid, which is the shape that makes an
interface look like financial software. The composition is written down in
fractions of the window rather than generated, so it is the same arrangement at
every size and can be adjusted by moving a number. Nothing in it uses randomness.

`Backdrop` is a component, not a picture of one screen: it fills whatever
surface it is handed and caches one rendering per size, so any other full-screen
menu can use it. Two things are worth knowing if it is ever changed:

- **Softness comes from scale.** Shapes are drawn small and scaled up, so their
  edges arrive blurred for the price of one smooth scale.
- **Masks are dimmed after they are scaled, never before.** At these strengths
  the whole alpha range is twenty-odd levels, and interpolating between those
  few values turns a gradient into a visible mosaic of the mask's own pixels.

Nothing in it rises above about a fifth of the brightness of the text in front
of it, and a test holds that line — a menu background that costs the buttons
their contrast is a worse menu than a plain one (V27.10).

New Game leads to the save-slot list before anything is created: five slots,
each marked EMPTY or IN USE with what it holds, none preselected, and an
occupied one confirmed before it is replaced. Naming the save is a popup, which
is modal on the menu exactly as it is in the game (V14.15).

## Behaviour standards (Volume 27)

| Rule | Where |
|---|---|
| Search filters as the player types, matching the most identifying field | `SearchBox`, `Table.visible_rows` |
| Sorting is explicit, reverses on reselection, and is remembered per list | `Table.sort_by` |
| Filtering combines additively with search | `Table.visible_rows` |
| One row per entity; numeric columns aligned in a monospaced face | `Table`, `Column` |
| A single click opens a row — never a double click | `Table.handle_event` |
| Breadcrumbs are always clickable, so no page is a dead end | `Breadcrumb` |
| Popups have a clear default and a clear cancel, and never stack decisions | `Popup`, `PopupManager` |
| Notifications sit lower-right, readable, and never stack out of view | `NotificationCentre` |
| Animation only clarifies a state change, and never delays the next action | `theme.SLIDE_MS` |
| Speed reachable by keyboard (1/2/3) as well as mouse | `app.SPEED_KEYS` |

## Popups pause the simulation (V13.20, V14.15)

Every popup pauses time, so a decision can never be made while the market moves
underneath the player. Because that pause is the cost of opening one, anything
not worth pausing for should be a notification instead.

Only one decision is put to the player at a time (V27.6); further requests queue
rather than stacking.

## Time controls (V14.18)

Speed is ×1/×2/×3 and always visible. There is deliberately **no pause button** —
the Design Bible allows pausing only through popups, so "Paused" is shown as a
state the player is told about, not a control they operate.

## Pages

| Page | State |
|---|---|
| Dashboard | Summary cards, recent activity, world conditions — no graphs by default (V14.14) |
| Company | Founding flow, statistics, capacity |
| Market | Searchable, sortable, paginated list of every listing |
| Company detail | Drill-down showing *why* a price moved, cause by cause |
| Financial Management | Report, expense breakdown, borrowing |
| Investments · News · Unlock Tree | Honest empty states — those systems are not built yet (V14.26) |
| Settings | Speed, and leaving the game |

## Three defects screenshots caught that tests did not

Rendering a page and *looking* at it found what assertions could not:

- **Every "Today" column read 0.00%.** The market records today's close before
  anything reads it, so the daily change compared today with itself.
- **Right-aligned headers collided with the next column**, because headers used
  a different inset from their own cells.
- **The sort marker rendered as an empty box** — the arrow character is missing
  from many system fonts. Sort markers and pagination chevrons are now drawn.
