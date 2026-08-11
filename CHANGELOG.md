# Changelog

All notable changes to Apex Horizon are recorded here, as required by Design
Bible V19.21. Entries cover features, improvements, refactors, bug fixes,
balance changes, and UI changes. Version numbers are set manually by the project
manager (V19.29).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- **Escape now retraces navigation history**, through the same back-stack
  the mouse side buttons already use, whenever the page itself has not
  already claimed the keypress for something else (closing a focused
  search box, for instance, which still happens first). One consistent
  meaning everywhere, rather than Escape doing something different — or
  nothing at all — depending which page happens to be open.
- **The Unlock Tree can now be zoomed, and shows a details panel for
  whatever node is selected.** Three discrete zoom levels (0.75x/1.0x/1.4x
  — discrete rather than continuous, since pygame's fonts are bitmap and a
  level between presets would blur rather than shrink cleanly), reachable
  by scroll wheel or the new +/-/Fit buttons; "Fit" jumps to the largest
  level that shows the whole tree at once. Clicking a node (as opposed to
  dragging the map, which a small movement tolerance now tells apart from
  a genuine click) selects it and opens a right-hand panel showing its
  name, description, cost, status, prerequisites by name, and what it
  unlocks — all read from the tree's own data, not a second hand-written
  copy of the same descriptions. This reverses an earlier decision to
  reject zoom entirely to protect V6.10's readability requirement — that
  requirement still holds, because scaling every node/spacing dimension by
  the same factor cannot change which row or column anything sits in, so
  it cannot introduce a line crossing that the un-zoomed layout did not
  already have, and text never renders below a legible preloaded size.
- **Buying a company outright moved to Company → Subsidiaries → Buy, and
  Subsidiaries is now its own unlock**, one leaf past Investment Funds
  (project manager ruling). The Market page's Acquire button is gone —
  Company → Subsidiaries now has its own "Buy a company" flow, listing
  every acquirable company and opening a purchase page (facts, price
  history, cost, one Acquire button) that calls the same
  `SubsidiaryBook.acquire()` the old Market button called; nothing about
  the acquisition itself changed, only where it's reached. The gate applies
  only to *new* acquisitions — a subsidiary already owned keeps earning
  income exactly as before, unaffected by whether the unlock is present.
  AI companies bypass the gate entirely, the same way they already bypass
  the Unlock Tree for training, since they never purchase unlocks.
- **Employee Management gained department tabs, filters, and a Performance
  figure.** Company → Employees now shows a tab per department (built
  generically off the Department enum, so a future department needs no UI
  changes to appear), with the breadcrumb reading Company → Employees →
  {Department} once one is selected. Status and minimum-skill filters sit
  beside the tabs, composing with the roster's existing search and
  column-sort rather than replacing them. A new Performance column shows how
  effectively each employee is actually contributing — skill weighted by
  department priority and happiness, the same figures the Investment System
  already uses internally — gated behind the existing but previously unused
  `performance_visible` unlock flag (Recruitment branch) rather than a new
  one. Sorting and filtering are display-only, as before; they never touch
  saved employee data.
- **Applicants take a few real simulated days to arrive, rather than
  appearing the instant "Find candidates" is clicked**, and the company can
  earn the right to screen and hire them on its own. Clicking "Find
  candidates" now schedules a pool (`employees.recruitment_delay_days`,
  4 by default) instead of drawing one immediately, and any candidates
  already waiting stay fully hireable while the new pool is on its way. A
  new unlock, **Automated Recruitment**, closes out the Recruitment branch:
  once bought, the Employees page offers an on/off toggle and a minimum-skill
  criterion, and while it's on the company keeps requesting and hiring
  candidates to that bar entirely on its own — through the exact same
  `hire()`/`refresh_applicants()` a manual click uses, never a separate or
  hidden hiring path, and manual hiring keeps working unchanged whether
  automation is on or not.
- **The mouse side buttons navigate back and forward**, the way they do in a
  browser. Every existing way of moving between pages — the sidebar, the
  breadcrumb, drilling into a row, a popup redirecting after an action —
  already goes through the one `GameApp.navigate()` method, so history is
  recorded there rather than as a separate system built just for the mouse
  buttons: each move extends the back history and clears whatever was
  available to go forward to, exactly like following a fresh link after
  going back in a browser. Save & Exit is an action rather than a
  destination (V16.4) and never calls `navigate()`, so it can never appear
  in history for either button to land on. Both buttons are inert while a
  popup or the developer console is open, and starting a new game or loading
  one clears the history from whatever session came before it, so back
  cannot reach across a load. Portfolio's own tabs (Personal, Company,
  Analytics, Statistics) stay page-internal state, untouched by this, the
  same as before.
- **The real Apex Horizon logo replaces two placeholder marks**: the window
  icon (previously unset) and the sidebar's "AH" text, at every width. A
  monogram-only crop is used at both sizes, since the full wordmark reads at
  Start Menu size but blurs away at a window icon or a 30-pixel sidebar mark.
  The image cannot recolour itself for hover the way the drawn nav icons do, so
  hovering the sidebar mark highlights a background pill behind it instead. The
  Start Menu itself keeps its text title, by project-manager choice.
- **New Game asks where the game should live.** The flow is now Start Menu →
  New Game → choose a save slot → name the save → Create Game. The slot list
  shows all five, each marked EMPTY or IN USE with the name, date and net worth
  of what is already there; nothing is chosen for the player, and an occupied
  slot is confirmed before it is replaced. The new game is written to its slot
  straight away, so it appears in the menu from the moment it starts.
- **A drawn Start Menu background.** Soft abstract geometry: a dark base with a
  slow gradient, one off-centre light, and faint overlapping shapes and lines.
  Deliberately not representational and with no grid, so it reads as depth
  rather than as financial software. The composition is written down in
  fractions of the window rather than generated, so it is identical at every
  size and on every launch, and it is a reusable `Backdrop` component any
  full-screen menu can use, cached per window size rather than redrawn each
  frame. Nothing in it rises above about a fifth of the brightness of the text
  in front of it, so the title and buttons keep the contrast they had.
- **An in-game developer console, opened with Ctrl+T.** V15.18 put developer
  commands in the launching terminal, which is no help to a packaged build or a
  desktop shortcut; the same commands now work inside the window. Both surfaces
  drive one command set, so neither can drift from the other, and the console
  executes nothing from the operating system — it understands its own commands
  and refuses everything else.
  - `money player` and `money company`, each with `set`, `add` and `remove`,
    accepting decimals and amounts written as `$1,250.75`. Company money goes
    through the company's own books, so the ledger stays truthful; with no
    company, it says so rather than failing.
  - `time`, `time set {year} {month} {week} {day}` and `time add {amount}{unit}`,
    which run the real simulation through every day rather than moving a label.
    Long jumps are spread across frames so the window keeps drawing, with the
    console counting the days down; `time cancel` abandons one.
  - `unlocks`, `unlock add` and `unlock remove`, going through the Unlock Tree
    and re-applying its effects. Granting a deep unlock grants what it requires
    and removing one removes what depended on it, so the tree never ends up in a
    state the game itself could not produce.
  - `help`, `help money`, `help time` and `help unlocks`, showing exact syntax.
  - It pauses the simulation while open, captures the keyboard so nothing leaks
    into the game behind it, shows commands apart from their output, colours
    refusals red, and cannot be crashed by anything typed into it.
- **A Start Menu.** The game now opens on one, with New Game, Load Game,
  Settings and Exit Game, and saved games listed with what V16.9 shows without
  loading the world. It is a menu rather than another dashboard.
- **Save & Exit follows V16.4 in full**: the simulation pauses, the save is
  attempted and validated, and only on success does the player return to the
  Main Menu. A failed save returns them to the running game with the error, so
  progress is never lost and another attempt can be made. Leaving a session is
  no longer leaving the program.
- **The sidebar expands.** Clicking the Apex Horizon wordmark shows the names
  beside the icons and clicking it again hides them; the choice is remembered
  for the session and the page moves aside rather than being covered. Tooltips
  stop once the names are showing, since they would only repeat them.
- **Save slot descriptions now show money, net worth, in-game date, and
  playtime together**, not net worth alone — every figure was already
  computed on `SaveSummary`/`SaveMetadata`, this only formats what was
  already there. Playtime reads in whichever unit fits its own size
  (minutes, then hours/minutes, then days/hours) rather than one fixed
  unit that reads oddly at either extreme. Shown wherever a slot is listed
  — Settings and the Start Menu's Load Game screen both read the same
  `SlotInfo.describe()`.

### Changed

- **No source file runs past 500 lines any more**, and `ui/app.py` — the one
  file allowed more room, since it is the application itself — is under 1,000
  (project manager instruction). Nothing changed behaviour: the suite runs the
  same 804 tests it did before, and no import anywhere else was rewritten.
  `ui/widgets.py` and `debug/commands.py` became packages whose `__init__`
  re-exports what they always did; the employee, subsidiary and Unlock Tree
  pages split by the screen they serve; `app.py`'s eleven modal dialogs moved
  to `ui/prompts.py`; and the six largest test modules became per-system
  directories with their fixtures in a local `conftest.py`, so each family
  keeps its own calendar setup instead of leaking it to every other test.

- **A save game now belongs to one slot for its whole life.** Autosaving used to
  write a separate rolling `autosave` file, which appeared in the Load menu as a
  sixth game the player had never started. Autosaving is now simply saving the
  game you are playing: it writes the slot chosen when the game was created, as
  do manual saves, Save & Exit and loading. The binding survives restarting,
  loading and closing the program because a game lives in the file it came from.
  Saving into a different slot moves the game there rather than leaving it
  autosaving somewhere the player has stopped looking, and Settings names the
  slot the game is saved in. A leftover `autosave.ahsave` from an older build is
  ignored rather than listed.
- **A save keeps the name the player gave it.** Saving no longer renames it
  after whatever the company happens to be called.
- **The game autosaves every ten real minutes** rather than every in-game month
  (project-manager decision). A month passes in twenty-eight seconds at normal
  speed and nine at triple, so the old rule saved constantly; the interval is
  now measured in the time the player actually spends, is adjustable in Settings
  (`save.autosave_interval_minutes`), and can be switched off. Time spent on an
  open decision does not count toward it, and V16.6's save before every
  irreversible decision is unchanged.
- **Companies no longer move around.** Listings are ordered by company id, which
  never changes, so a company holds the same position for the life of a save —
  prices moving, one company overtaking another, and reloading cannot shuffle
  the list. The Market list no longer sorts itself by size by default; it sorts
  only when the player clicks a column (V27.3).
- **Top gainer and loser are measured over a defined period**, seven days by
  default, rather than over a single day. The calculation was always correct and
  deterministic, but one in-game day passes every real second, so a daily figure
  changed about once a second and read as random however it was computed. Both
  now show the change and the period they cover, and there is a Top loser card
  to match the gainer.
- **Notifications appear in the lower right**, clear of the sidebar, which has
  to stay usable while a message is showing.
- **Settings sits above Save & Exit** at the foot of the sidebar, apart from the
  systems above them.

### Fixed

- **Notifications are a floating overlay again, and no longer move the
  interface.** A message arriving used to shrink the page it appeared over —
  the lower-right corner was reserved out of every page's content area, so
  panels, tables and buttons all shifted up as a message arrived and dropped
  back as it expired, leaving an empty band across the bottom of the window
  meanwhile. Nothing is reserved now: the page is laid out at the full height
  of the window whatever is showing, and the stack is simply drawn on top of
  it afterwards. Messages still arrive, stack upward from the bottom right,
  slide, expire and read exactly as before — they just no longer disturb
  anything underneath them (project manager ruling, reversing the 2026-08-09
  reservation).
- **Save slots are named after the game saved in them**, in both Load Game and
  the New Game slot chooser, rather than every row reading "Slot 1" … "Slot 5"
  and leaving the player to tell five identical labels apart by the figures
  underneath. "Slot N" remains the name of a slot with nothing in it to name.
  The details beside the name no longer repeat it.
- **The Unlock Tree follows the roadmap layout** the legacy prototype's
  reference image lays out (layout only — colours and styling stay Design
  Bible 2.0's): one spine straight through the middle carrying Basic
  Investing, Create Company, the Company Levels and Investment Funds, with the
  branches fanning symmetrically above and below it, and Analytics and News
  outermost since they come off Basic Investing rather than off a company. The
  spine previously sat near the top with every branch hanging beneath it.
  Where the branches converge on Investment Funds they now share one vertical
  rail instead of each drawing its own elbow, so seven incoming lines read as
  a single junction rather than a fan.
- **The shared Cash card no longer shows cents.** Every other summary card
  rounds to whole dollars; the Cash card was built with `.format()`'s own
  two-decimal default, so the figure the player reads most often was the one
  that looked different from its neighbours.
- **The Market page names its own empty state** ("No companies are listed on
  the market right now.") instead of falling back to the generic Table
  message, which read oddly for a page that normally always has listings.
- **Button tooltips now actually show.** `Button.tooltip` has existed since
  buttons could carry one, but nothing ever read it. Hovering a button with a
  tooltip set now shows it with the same small label the sidebar already uses
  for its icons — applied to Employee Management's automation Criteria
  button and the Unlock Tree's Fit button, where the label alone does not say
  what the button does.
- **One spelling for a percentage.** Reputation, investor confidence,
  happiness and performance were each formatted with a different pattern
  (`:.0%` in some places, `value * 100:.0f}%` in others) for the identical
  visual result. All four now go through one small helper.
- **A save slot's date reads exactly like the in-game date everywhere else.**
  `SaveSummary.date_label()` reimplemented `SimulationDate.label()`'s format
  string independently; it now shares it, so the two can never drift apart.
- **Settings, Subsidiaries and Investment Funds no longer let a panel spill
  into the notification stack.** Each used a fixed pixel height that did not
  shrink with the rest of the page the way Dashboard, Employee Management,
  News and the Unlock Tree's info panel already did, so on a short window
  with several notifications showing, a panel could render past its own
  reserved space — in the worst case landing a control (a save slot's
  Save/Load buttons, the bootstrapping Buy/Open/Acquire button for a
  player's first subsidiary or fund) underneath the notifications rather
  than above them. Panels now clamp to the room they actually have, and the
  one control each carries gets priority over the descriptive text beside
  it — matching the rule the Employee department bar already follows —
  rather than the two being allowed to overlap each other.
- **The Hire button now actually hires.** Every candidate's button was recreated
  from scratch on every draw, and a click spans two frames — down on one, up on
  the next — so the fresh button on the second frame had no memory of the press
  the first one saw, and the release was silently ignored. It now keeps one
  button per candidate across frames, matching the pattern the rest of the
  interface already uses for per-row buttons. `EmployeeRoster.hire()` itself —
  capacity, applicant removal, statistics, saving — was already correct; only
  the click was ever lost. Covered by tests that drive the button through real
  mouse-down/mouse-up events with a draw between them, and by a save/load round
  trip through the same dispatcher the button uses.
- **Personal cash is now shown on every screen**, as the first summary card on
  every page, styled exactly like the figures beside it. It is drawn by the shared page layout rather than by
  each page, so no screen can omit it and it cannot drift out of position. It
  is personal cash specifically — never net worth, which counts holdings and a
  company that cannot be spent, and never the company's own cash, which stays
  where it was (V1.4).
- **A market where nothing rose no longer reports a top gainer.** Both the
  Dashboard and the Market page were labelling the least bad loser as the top
  gainer, in green, on a day when every company fell. They now say so plainly.
- The Dashboard showed the top gainer's name with no figure beside it, which
  gave the player no way to see the choice meant anything — and since it changes
  every in-game day, it read as arbitrary. The change is now shown with it.
- Ties for top gainer are broken on company id rather than on whatever order
  the listings happened to be held in. The result was already stable, but by
  accident rather than by design.

- Tables now fit a page to the space the panel actually has, rather than always
  drawing twelve rows. A fixed count ran past the bottom of the panel on a short
  window, which reads as a broken list rather than a full one.
- **A bankrupt company can no longer operate.** `GameContext.has_company`
  (already the correct check in a few places) is now used everywhere a page
  needs to know whether there is a business currently running, rather than
  only whether a company object exists — a bankrupt company still exists, by
  design, as a historical record (V1.3), so `company is not None` was never
  the right test for "is it open for business". Dashboard, Company, Financial
  Management, Employees, Subsidiaries and Investment Funds all now show the
  bankruptcy for what it is instead of stale live figures, and
  `EmployeeRoster.hire()` itself refuses a bankrupt company, matching the
  refusal `SubsidiaryBook.can_acquire()` and `FundBook.can_create()` already
  gave theirs — the state check was missing, not just the button. The Company
  page's bankruptcy notice no longer overlaps the Employee Management button;
  it is now part of the page's normal empty state rather than a caption
  drawn over the top of it.
- **Notifications can no longer cover Hire buttons, table rows or dashboard
  figures.** The stack still slides in at the bottom right (unchanged,
  unhidden, un-shortened), but the page beneath it now gives up exactly the
  room the current stack needs (`NotificationCentre.safe_height`), and every
  affected page's layout is adaptive rather than fixed-height: Employee
  Management prioritises its Candidates panel and, rather than silently
  hiding the staff table when there is no room for it, reclaims a small
  amount of Candidates' own space — unless Candidates is already at its own
  compact floor — so there is always enough room to say the table is hidden
  instead of leaving an unexplained gap where it used to be. The Dashboard's
  two side panels clamp to the space they are actually given. A reservation
  sized to the worst case at all times was tried first and rejected — it
  permanently left the Employee Management staff table with no room at all
  at the minimum window size, even with nothing showing.
- **A table too short to hold its forced single row no longer draws its page
  count and page controls on top of it.** `_rows_that_fit` always shows at
  least one row rather than none, which the pagination footer — positioned
  from the bottom of the panel — could end up overlapping on a short window.
  The footer now goes unshown rather than overlapping when there is no room
  for both.
- **The News page's lead story and archive no longer overlap themselves or
  spill past their own panels under a short window.** The lead story used to
  keep a fixed height regardless of how much room the page actually had,
  which could leave the archive with space for a single row, or shrink the
  lead itself far enough that its byline was drawn on top of its own body
  text; the archive's own "Archive" heading and hint line had no such guard
  either, and could be drawn spilling past the bottom of a panel shrunk to a
  couple of dozen pixels. The archive now keeps priority the same way
  Employee Management's Candidates panel does, the lead story drops its body
  and byline, in that order, and the archive's heading goes unshown below its
  own minimum — none ever laid over something else.
- **Analytics and Statistics no longer carry a dead `key`.** Both are tabs
  inside Portfolio — composed by calling `draw_content` directly rather than
  through the shared `Page.draw` — and were never registered as sidebar
  destinations, so the `key`, title and subtitle they inherited from `Page`
  looked like a real, reachable page while doing nothing if anything ever
  navigated to them. Removed rather than registered, matching how the rest of
  Portfolio's tabs already work.

### Known gap

- A company can appear more than once in one investment fund's position list.
  This is **not confirmed as a bug** — it may be genuinely separate purchases,
  which is legitimate for a position list to show — and was deliberately left
  alone rather than changed on the strength of looking cluttered (V19.4). See
  `docs/design-decisions.md`.
- Long automated playthroughs were observed getting slower, but this has **not
  been profiled**, so the cause is unknown and nothing was changed on the
  strength of the observation. A dedicated profiling pass is needed before any
  optimisation. See `docs/design-decisions.md`.

The top gainer itself was **not** randomly selected: it was already ranked on
the largest actual daily change, and a test now pins that, including one that
fails if the ranking ever consults the random number generator.

### Changed — presentation and navigation (PM corrections)

Two project-manager corrections made after playing the build. Both are
presentation only: no gameplay system changed, and the reasoning is recorded in
[`docs/design-decisions.md`](docs/design-decisions.md).

**Visualisation.** V14.3 names business dashboards as an inspiration, and the
interface had been building tables instead. Added a charts module — sparklines,
meters, comparative bars, line charts — and put it to work:

- A company's page now shows its **price history** as a chart. The market had
  been keeping two years of closes for every listing and showing the player one
  of them.
- The seven causes of a price move are drawn as comparative bars rather than
  seven signed percentages, so the explanation V4.21 requires is visible at a
  glance rather than reconstructed from decimals.
- Cards carry an accent, a trend direction and, where the figure is really a
  proportion, a meter. States like the economy and market mood read as status
  chips rather than as grey text identical to every other value.
- Charts appear only on pages the player opens deliberately, never in default
  views, as V14.7 and V14.14 require.

**Navigation.** Ten sidebar entries listed screens rather than systems. The
navigation is now Dashboard, Market, Portfolio, Company, Unlocks, News,
Settings, with **Save & Exit** separated at the foot of the sidebar because
leaving is an action rather than a destination (V16.4).

- **Portfolio** gathers every holding: Personal and Company behind a selector,
  plus Analytics and Statistics. The company view appears only once a company
  exists and never replaces the personal one (V1.19, V1.20).
- **Company** gathers the business: overview, employees, financial management,
  subsidiaries and funds.
- Nothing became unreachable; a test asserts every system V14.5 names can still
  be opened.

### Fixed

- A summary card's value and detail line overlapped when the card carried a
  meter.
- A card showed a green upward arrow for a change of exactly zero.
- Comparative bars dropped the final row when it would not fit, which was the
  row that usually set the scale — leaving every visible bar measured against a
  value that had been cut off, and drawn as a sliver.

### Added — Milestone 16: Statistics & developer tooling (V28, V15.18)

Documented in
[`docs/statistics-and-tooling.md`](docs/statistics-and-tooling.md).

- **Lifetime statistics** (V28.7): cumulative figures across a whole
  playthrough, kept as permanent never-reset records — profit and losses ever
  taken, employees ever hired, companies founded, lost and acquired, funds
  opened, trades made, and the highest net worth and company value ever reached.
  A company can go bankrupt and be founded again without touching any of them,
  because they describe the playthrough rather than the company.
- **A Statistics page** gathering the categories V28 catalogues — lifetime,
  company, investments and the world — in one place.
- **The terminal developer console** (V15.18): commands typed into the terminal
  that launched the game, covering every capability the volume names — money,
  time, employees, research, market events and the economy — plus unlocks and a
  status summary. A daemon thread reads the terminal so the simulation never
  blocks, and commands run on the main thread so one can never change the world
  halfway through a frame. It stays inert wherever there is no terminal, which
  is every test and CI run, and a typo is reported rather than ending the game.
- Counters are fed through callback lists systems already expose, so nothing in
  the engine knows the statistics module exists (V15.7).

### Fixed

- Several lifetime counters were defined but never connected, so the Statistics
  page showed "Profit ever made $0" beside "Realised $3,598,463". Closed
  positions, amounts invested, management fees and high-water marks are now
  actually recorded. Building the page is what exposed it — a recorder nothing
  calls looks correct in any test that only exercises the recorder.

### Added — Milestone 15: Investment Funds (V11)

The last system in the Unlock Tree, and the one that changes what the company
is. Code lives in `apex_horizon/engine/funds/` and is documented in
[`docs/investment-funds.md`](docs/investment-funds.md).

- **The money is not the company's** (V11.5). A fund holds its own finances,
  entirely separate, and assets under management are deliberately *not*
  registered as a company asset — managing money is not owning it. The company
  owns only the fee it has earned, which is the one thing that crosses from a
  fund to the company. Investor capital is recorded as financing rather than
  revenue, since the fund was entrusted with it (V17.26).
- **Composition, not duplication** (V11.23). The investment workflow only asks
  its owner whether it is bankrupt, who its employees are, and for its finances,
  so a fund supplies those three and runs the identical V8.3 process (V11.9).
  There is no fund-specific investing code at all — the third system built this
  way, after AI companies and subsidiaries.
- **Confidence grows funding on its own** (V11.11, V11.20). Investors judge the
  record, confidence moves slowly toward what the fund's return justifies, and
  above a threshold they add money each month without the player doing anything.
  Measured over five years: $250,000 grew to $916,000, confidence 50% to 89%,
  $51,645 paid to the company in fees.
- **Several funds at once** (V11.7), each independent, each with its own
  management page showing performance, history, assets and active investments
  (V11.13). An empty new fund is presented as a valid state, because V11.21 says
  it is one.
- **The final unlock now opens something** (V11.3, V6.8). Investment Funds was
  drawn but unbuyable; it is now the real capstone the tree always described.

### Known gap

- V11.21 leaves undefined what should happen to a fund that becomes deeply
  insolvent. Nothing is invented: confidence collapses and funding shrinks, and
  a fund is never bankrupt in its own right.

### Added — Milestone 14: Acquisitions & Subsidiaries (V12)

The company can now buy other companies outright. Code lives in
`apex_horizon/engine/acquisitions/` and is documented in
[`docs/acquisitions.md`](docs/acquisitions.md).

- **Ownership, not a second model** (V12.23). Acquiring a company sets the
  ownership reference the world's company record already carried; the subsidiary
  record holds only what ownership adds — what was paid, what it is worth, and
  what it has paid up.
- **Paid in full, in company cash** (V12.4, V12.22): never personal money, never
  financed, and an attempt that cannot be afforded is refused with a reason
  rather than driving the balance negative (V12.21). Buying a business is an
  exchange of cash for an asset, so it never touches profit (V17.26).
- **Subsidiaries keep operating** (V12.5) in their own industry, paying their
  parent monthly. What they pay and what they are worth follow that industry's
  fortunes, which is what makes a poor acquisition genuinely poor (V12.11).
- **An acquired company is delisted** (PM ruling): owning it outright leaves
  nothing to trade, so it leaves the market the same way any company does.
- **A Subsidiaries page** (V12.9) with a searchable, sortable list opened by a
  single click, and a page per subsidiary showing the business, what it cost,
  what it is worth and what it has paid (V12.8).
- **AI companies acquire too** (V12.14), using the identical rules, gated by
  company size like the player's (PM ruling) so the early market stays open.

### Fixed

- **Market capitalisations were fifty times too large.** Listed companies were
  worth tens of billions while a mature investment company is worth single-digit
  millions, so an acquisition could not have happened at any point in any
  playthrough. Shares in issue are rescaled so the cheapest companies cost
  around $10M — reachable late, while the median stays beyond any one buyer.
- **The investment system's cash reserve did not survive growth.** It kept back a
  flat $2,500, which is meaningful to a company founded with $25,000 and nothing
  to one worth millions: such a company stayed permanently fully invested and
  could never accumulate the cash an acquisition must be paid with. The reserve
  is now the larger of that floor and a share of the whole portfolio — measured
  against the portfolio rather than cash, since measuring against cash makes the
  reserve decay toward nothing as it is spent.
- An AI company's acquisition review was nested inside its hiring review, so it
  only ran on the rare day both cadences coincided — once every 630 days rather
  than every 90.

### Added — Milestone 13: AI Companies (V26)

The world now has other investment companies in it. Code lives in
`apex_horizon/engine/ai/` and is documented in
[`docs/ai-companies.md`](docs/ai-companies.md).

- **They are ordinary companies** (V26.10). An AI company is an instance of the
  same structure the player's company uses, differing only in that its decisions
  are generated rather than taken by a person. There is no AI company class —
  only an `AIDirector` operating a normal `InvestmentCompany`. Investing runs
  through the identical V8.3 workflow (V26.7), orders reach the market as
  ordinary demand (V26.8), and solvency follows the same financial rules
  (V17.18).
- **`PlayerCompany` is now `InvestmentCompany`.** It is no longer the player's
  alone, and a name implying otherwise would mislead the next reader.
- **A population, not an opponent** (V26.11). Each company draws its own bias
  toward risk, which shifts the distribution of the hidden characteristics its
  employees are generated with (V5.7) rather than forcing an outcome — so AI
  staff skew bolder than the player's on average (V26.4) while some companies
  still end up conservative (V26.3). Over fifteen in-game years the strongest
  firm reached $2.8M and the weakest fell below zero.
- **They hire and grow** (V5.18, V18.16). A director staffs its weakest
  department first, keeps months of payroll in reserve before hiring again, and
  raises its Company Level as the company becomes worth more — the procedural
  equivalent of the player buying Company Level unlocks, which keeps growth an
  emergent outcome of investing well (V26.5, V18.17).
- **Competition is never adversarial** (V26.6). No AI company knows the player
  exists; they simply act, and an opportunity hesitated over may be taken first.
- **The dashboard shows them** by name, value, staff and level, with where the
  player ranks among them — V4.10 says the market does not revolve around the
  player, which is hard to believe from a screen where nobody else appears.

### Fixed

- Saving XOR'd its payload a byte at a time in Python, which made autosaving the
  single most expensive thing the simulation did — more than every company in
  the world combined. Doing it a machine word at a time roughly halved the cost
  of simulating a year.
- AI directors' random streams were not saved, so a reloaded world took
  different decisions from the one that was saved (V15.11, V16.28). This is the
  third time this class of bug has appeared; the rule is now written down in
  `docs/ai-companies.md`.

### Added — Milestone 12: the Unlock Tree (V6)

The whole tree of Volume 6, and the effects behind it. Code lives in
`apex_horizon/engine/unlocks/` and is documented in
[`docs/player-and-progression.md`](docs/player-and-progression.md).

- **All 32 unlocks** (V6.5–V6.8): the primary progression, the Analytics and
  News branches off Basic Investing, the five Company Level 2 branches in the
  order V6.7 states, and Investment Funds where every branch converges. Contents
  are kept in a catalogue separate from the machinery that reads them.
- **Every unlock does something** (V6.3). Analytics and News open their pages and
  deepen through their tiers; Finance opens borrowing and improves lending terms;
  Employees raises applicant skill ceilings to 20/30/40 exactly as V6.7.2 states;
  the Company branch drives Company Levels 2–5 and then Company Analytics (V9.9);
  Training opens training and makes it teach faster; Recruitment widens the
  applicant pool, makes reputation count for more, and reveals hidden strengths
  and performance. A test asserts each purchasable unlock measurably changes the
  game, naming the two deliberate exceptions.
- **Effects are pushed, not pulled**: systems never ask the tree what the player
  owns, so no gameplay system knows progression exists (V15.7) — and the whole
  configuration is re-applied after loading, so a restored game behaves exactly
  as the saved one did.
- **Analytics gains a fourth tier** and a Company Analytics report of department
  performance and operational efficiency (V9.9), so the branches that end in them
  have something real to open.
- **News and analytics are now earned**, not given: before Basic News there is no
  financial press at all, and before Basic Analytics no Analytics page. Both say
  so plainly rather than showing an empty screen (V14.26).
- **The tree page** is a pannable roadmap (V6.10): straight horizontal
  connections, elbows onto shared verticals so no two lines cross, branch names
  in a fixed gutter, and every node showing its state and price.
- **Prices scale from one number** — each unlock declares its depth and takes a
  multiple of the company founding cost, so retuning the founding cost rescales
  the whole tree ($5,000 at the roots to $1,000,000 at Company Analytics).

### Fixed — the player and their company are separate entities (V1.4, V3.4)

A correction to a mistaken reading that ran through several systems. The game
treated company ownership as the starting state, so the first two stages of the
intended progression did not exist at all — a player who began with $10,000 and
needed $25,000 to found a company had no way to earn the difference. The
progression is now enforced end to end, and documented in
[`docs/player-and-progression.md`](docs/player-and-progression.md):

> Start → Individual Investor → Build Personal Wealth → Unlock Create Company
> → Pay $25,000 → Found Company → Build Company

- **Personal investing** (V1.19, V1.20), which did not previously exist. The
  player buys and sells shares with their own cash from the first day, with or
  without a company — V1.20 makes remaining an individual investor a valid
  playstyle, not a tutorial. Cost basis is tracked per holding, so selling part
  of a position leaves the rest carrying its own share of what was paid, and
  gains are measured against money actually spent.
- **Personal orders reach the market** through the same recorded demand the
  company uses (V4.8), so buying moves a price rather than drawing on an
  infinite pool.
- **Create Company is an unlock** (V6.2, V6.4). Founding is refused until it is
  bought, and the refusal explains itself rather than presenting a dead button.
  Unlocking grants permission only: founding remains a separate decision costing
  $25,000, unchanged.
- **The Unlock Tree** now exists as the directed acyclic graph V6.19 asks for,
  with prerequisites as explicit edges and every price read from configuration.
  Only Basic Investing (owned from the start, V6.4) and Create Company are
  listed: V6.3 requires an unlock to change something, so the remaining branches
  arrive with the systems they gate, and the page says so.
- **Personal net worth** now counts personal holdings alongside cash and company
  value (V1.6), while the two pools of money stay separate (V1.4).
- The Investments page leads with the player's own portfolio and shows the
  company's operation beneath it, so the separation is visible rather than
  implied.
- The Company page, before a company exists, shows the route to one as numbered
  steps with the player's position on each, rather than a disabled button. The
  individual-investor phase is long by design (see below), so it has to read as
  a plan being worked through rather than a refusal (V14.26).

### Balance — the individual-investor phase is long by design (PM decision)

Measured across six worlds, a diversified buy-and-hold position returns a median
6.1% a year, so tripling $10,000 into the $30,000 a company needs takes about 18
in-game years. V1.19's example describes "several in-game weeks". Shown the
measurement, the project manager ruled that the long phase is intended and the
$25,000 founding cost stands (V1.20 makes remaining an individual investor a
valid playstyle). No personal income mechanic was added: the Design Bible
describes none, and inventing one would be a new mechanic rather than an
implementation detail (V15.9).

Unlock prices are derived from the founding cost rather than written
individually, so the whole tree stays in proportion whenever any of it is
retuned (`unlocks.cost_multipliers`).

### Fixed

- Saving used a fixed temporary filename, so the atomic write was only atomic
  within one process: two games sharing a save directory would write the same
  temporary path, and the first to finish moved the file out from under the
  second, which then failed with the old save already replaced. The temporary
  now carries the writing process's id, and a failed write cleans up after
  itself instead of leaving a stray file behind (V16.19).
- `change_over` reported 0.00% when a listing had not traded long enough to
  know, which is indistinguishable from a price that genuinely had not moved —
  a company listed last month read as flat over the past year. It now reports
  nothing, and the interface shows a dash. Industry averages count only the
  listings that have the history, instead of being dragged toward zero by new
  ones.
- News was missing from the price breakdown on a company's page, despite being
  added as a distinct cause (V4.4); the seventh row was also cut off by the
  panel it was drawn in.

### Added — Milestone 11: News & Analytics (V10, V9)

The world now reports on itself, and the game reports back to the player. Code
lives in `apex_horizon/engine/news/` and `apex_horizon/engine/analytics/`, and is
documented in [`docs/news-and-analytics.md`](docs/news-and-analytics.md).

- **News generated from real events** (V10.9, V10.24): the News System runs
  first in the day (V29.3) over *yesterday's* settled data, so every headline
  describes something that genuinely happened. Company moves past 4.5% are
  reported, 6% is breaking, the market is surveyed weekly, and the economy is
  reported when it turns.
- **Bylines from the world** (V33.10): each story is attributed to one of the
  world's own news agencies, with financial specialists preferred for market and
  economic stories.
- **News moves prices** (V10.10): a story pushes the company it concerns for a
  few days, decaying as it ages. V4.4 lists news as a distinct cause of price
  movement, so `PriceChange` now carries a separate `news` term instead of
  folding it into sentiment — which is what lets the market name the news as the
  reason for a move (V4.21).
- **The archive, not a ticker** (V10.15): the last 120 stories stay readable on
  the News page, filterable by tier, with the selected story shown in full.
- **Tiered coverage** (V10.4, V10.16): Basic, Market, Economic and Breaking are
  raised through the Unlock Tree. A locked tier is genuinely withheld rather
  than shown in reduced detail.
- **Analytics across five views** (V9.5–V9.10): the company, its employees, the
  market, investments, and change over time — each gated by an analytics tier
  that adds depth rather than access. A report whose subject does not exist yet
  is absent rather than empty (V9.21).
- **Historical tracking** (V9.10): nothing else in the simulation remembered the
  past. A monthly snapshot of net worth, cash and the market index is now kept
  and charted, capped at `analytics.history_limit`.
- **Analysis stays out of the simulation** (V9.22): reports are plain data, and
  the page that draws them knows nothing about how any figure was reached.

### Fixed

- **Reloading a game could change its future** (V15.11, V16.28). The world
  generator's and name generator's random streams were not saved, so they
  restarted from the seed on every load — meaning a company listed after loading
  differed from the one an uninterrupted game would have listed. Both now carry
  their stream position in the save. Saves written before this change still
  load.
- **Breaking news could never happen.** The threshold was set at a 12% daily
  move, sized against the 25% price clamp rather than against what the market
  actually does: over 45,733 observed daily moves the median was 0.72% and the
  largest 7.23%, so the Breaking News unlock would have bought the player
  nothing. Lowered to 6%, just past the 99.99th percentile — measured at about
  2.6 genuinely extraordinary sessions a year.
- Headlines reporting a fall read "down -4.5%", a double negative, because the
  template already supplied the direction. The figure is now written unsigned.

### Changed

- Only breaking news and shifts in the economy raise a notification. Every
  article did, which buried the screen in toasts and made the story that
  mattered no easier to notice than the rest (V10.14, V14.16).
- The sidebar gains an Analytics section, which V14.5 permits ("additional
  sections may be added as the game expands").

### Added — Milestone 10: Investment System (V8)

The company now earns. Code lives in `apex_horizon/engine/investments/` and is
documented in [`docs/investments.md`](docs/investments.md).

- **The full workflow** (V8.3): research discovers, management approves or
  rejects, an investor executes, the position is held, and the investor
  eventually sells. Each stage is independently timed, so a partly-completed
  workflow is a valid inspectable state (V8.24). It runs in the Employees phase
  so its demand reaches the market the same day (V29.10, V4.8).
- **Research is where skill pays** (V8.4, V9.5): a researcher compares several
  candidates and favours the one whose underlying business is performing. With
  skilled staff the companies chosen averaged +0.26 performance against a market
  average of −0.11, giving +6.4% per closed position at a 60% win rate — an
  edge, never a guarantee (V8.12).
- **Correct accounting**: buying is not an expense but an exchange of cash for
  an asset, so it never touches profit; selling books returned capital as
  financing and only the difference as profit or loss (V17.26, V9.12).
- **Limits and constraints** (V8.8, V8.22): per-investor limits, a position
  ceiling, and approved opportunities that wait rather than forcing a negative
  balance. Position size and sell targets come from hidden characteristics
  (V8.13).
- **Investments page**: open positions with unrealised gain, and the pipeline of
  what is awaiting review or execution.
- **25 further tests** (421 total).

### Fixed

- Salaries and running costs were wildly out of scale for a company founded with
  $25,000 — three employees cost more per year than the company would ever hold.
  Both are recalibrated so a first hire is affordable and payroll becomes a
  serious cost only as the organisation grows.
- Research had no predictive power, which meant buying with a target and a stop
  in a randomly moving market had no expected value: the company could never
  become profitable no matter how well it was run. Research now genuinely
  selects better-performing companies, in proportion to the researcher's skill.

### Added — Milestone 9: Employees & Company Management (V5, V18)

The company now has people. Code lives in `apex_horizon/engine/employees/` and
is documented in [`docs/employees.md`](docs/employees.md).

- **Three skills, three departments** (V5.4, V5.5): every employee has all three
  and is assigned a primary, secondary and third priority, performing best in
  their primary. One generalist can run an early company while specialisation
  still pays off later (V5.6).
- **Recruitment** (V5.3): candidates drawn from the same population as the rest
  of the world, with reputation shifting the distribution rather than
  guaranteeing quality. Skill ceilings follow the Better Employees tiers of
  V6.7.2.
- **Development and training** (V5.8, V5.9): experience accrues where work is
  done, so employees improve fastest in their primary department. Training is
  measured entirely in days and survives week and month boundaries.
- **Pay and morale** (V5.10, V5.11, V5.24): happiness follows pay measured
  against what an employee now believes they are worth. Because expectation
  derives from current skills, leaving a strong employee on their starting
  salary slowly costs performance rather than saving money for free.
- **Timeline** (V5.16): the previous ten in-game days per employee.
- **Capacity and bankruptcy**: capacity follows Company Level; on bankruptcy
  training is cancelled and staff released, wired through the company's
  bankruptcy callback so neither system knows the other's internals.
- **Interface** (V5.14, V5.15): Employee Management behind Company → Employees,
  with a searchable sortable list, and a details page carrying skills,
  department dropdowns, training, pay, timeline, and hidden characteristics
  gated until the Recruitment unlocks reveal them.
- **34 further tests** (396 total).

### Fixed

- Employee development was effectively invisible: at the original experience
  cost an employee gained nothing in a full in-game year, contradicting V5.8.
  Recalibrated to a little over one skill point a year in a primary department.
- Timeline markers used decorative glyphs that render as empty boxes in many
  system fonts — the same class of defect already fixed for sort markers.
  Markers are now plain ASCII.
- Repeated identical notifications now refresh rather than stacking, so routine
  messages such as autosaves cannot crowd out ones the player has not read
  (V27.7).

### Added — Milestone 8: Save System (V16)

Progress is now safe. Code lives in `apex_horizon/engine/save/` and is
documented in [`docs/save-system.md`](docs/save-system.md).

- **File format** (V16.18–V16.20): structured JSON, compressed, with a light
  obfuscation pass and a checksum. Small files that are not casually editable —
  explicitly not security, and not presented as such.
- **Atomic writes**: saves are written to a temporary file and moved into place,
  so an interruption mid-write cannot destroy the save that already existed.
- **Five manual slots plus one rolling autosave** (V16.7, V16.8), each an
  independent world, each carrying its own summary so a slot can be listed
  without loading it (V16.9). A slot that cannot be summarised is shown as
  damaged rather than hidden.
- **Validation, migration and repair** (V16.13–V16.15): an invalid save never
  silently loads. A damaged file has its contents salvaged where possible and
  the player is asked whether to try anyway; older formats migrate through a
  registry; repair is conservative and reports what it did.
- **Everything that affects gameplay is saved** (V16.11), including every
  listing's full price history (V4.22) and the generation state, so companies
  created after a reload never collide with earlier ones.
- **Autosaving** (V16.5, V16.6, V16.24): monthly by default, adjustable and
  switchable off, plus an autosave immediately before a major irreversible
  decision, with a brief non-pausing notification.
- **Save & Exit** (V16.3, V16.4): no standalone Save button; the workflow pauses,
  saves, and leaves only if that succeeds — a failed save returns the player to
  the running game rather than losing the session.
- **Export and import** (V16.21, V16.22), with an import refused before it can
  overwrite a slot if the file cannot be read.
- **World serialisation**: the world is generated from a seed but keeps growing
  during play, so its entities are saved rather than only the seed.
- **Slot management in Settings**, keeping the navigation V14.5 specifies
  unchanged.
- **46 further tests** (362 total), including a save, replay and reload that
  asserts every share price matches (V15.11, V16.28).

### Added — Milestone 7: User Interface framework (V14, V27)

The game is now visible and clickable. Code lives in `apex_horizon/ui/` and is
documented in [`docs/user-interface.md`](docs/user-interface.md).

- **Visual language** (V1.15, V14.3): a near-monochrome dark palette drawn from
  professional financial software, with colour reserved for meaning — one accent
  for the active element, green and red only for gain and loss. Everything
  visual comes from `theme.py`.
- **Icons** (V27.10): monochrome outline icons drawn rather than loaded, so the
  set stays one family and nothing can go missing at runtime. Every icon is
  paired with a label or tooltip.
- **Shared page layout** (V14.20, V14.28): header, breadcrumb, summary cards,
  search, content — positioned by the base `Page` class rather than by each
  page, so consistency is structural.
- **Sidebar and breadcrumbs** (V14.4-V14.6, V27.4): the eight sections V14.5
  names, and a clickable path so no page is ever a dead end.
- **Tables** (V14.8, V14.17, V27.2-V27.5): search that filters as you type,
  explicit sorting remembered per list, pagination, numeric columns aligned in a
  monospaced face, and a single click to open a row.
- **Popups** (V13.20, V14.15, V27.6): every popup pauses the simulation, offers
  a clear default and cancel, and only one decision is shown at a time.
- **Notifications** (V14.16, V27.7): lower-left, sliding in and out, never
  pausing the game, never stacking beyond what can be read.
- **Time controls** (V14.18, V27.9): ×1/×2/×3 always visible and reachable by
  keyboard, with no pause button — pausing happens only through popups.
- **Pages**: Dashboard, Company (with the founding flow), Market, a company
  drill-down showing *why* a price moved cause by cause, Financial Management,
  Settings, and honest empty states for the systems not yet built (V14.26).
- **29 further tests** (316 total), exercising real layout and rendering.

### Fixed

- Every "Today" column read 0.00%: the market appends today's close before
  anything reads it, so the daily change was comparing today with itself. Past
  prices were off by one day for the same reason.
- Right-aligned table headers collided with the next column, because headers
  used a different inset from their own cells.
- The sort marker rendered as an empty box — the arrow character is missing from
  many system fonts. Sort markers and pagination chevrons are now drawn rather
  than typed.

### Added — Milestone 6: Company & Financial Management (V3, V17)

The player can now found and run a company. Code lives in
`apex_horizon/engine/company/` and is documented in
[`docs/company-and-finances.md`](docs/company-and-finances.md).

- **Player and company as separate financial systems** (V1.4, V3.4): personal
  cash may move into the company and never back out. The rule is enforced
  structurally — `transfer_to_company` has no counterpart anywhere in the code.
- **Founding** (V2.4, V3.3): costs $25,000 against a $10,000 starting purse, so
  the player must build capital first. The cost becomes the company's opening
  capital by default, since a company founded with nothing could not act at all.
- **The append-only ledger** (V17.27): every movement of money records an entry,
  and the week, month, year, lifetime, per-category and cash-flow totals are all
  updated by that same call — consistent by construction rather than by
  discipline. Bounded for saves (V16.20) while lifetime totals persist.
- **Financial figures** (V17.6-V17.12): revenue, categorised expenses, profit,
  assets, liabilities, net worth, and company value with goodwill from sustained
  profit. Assets held by other systems arrive through registered providers, so
  each system keeps its own data (V15.7).
- **The company through time** (V13.9-V13.11): weekly operating costs and loan
  repayments, monthly closes, yearly profit tax. Reputation drifts toward
  sustained profitability in small steps, so trust is earned (V3.8).
- **Levels and capacity**: Company Level is raised by Unlock Tree purchases
  (V6.7.3), not automatically; capacity follows at 10/25/50/100/200.
- **Loans** (V17.13): terms come from the banks of V7.10, so borrowing already
  follows the economic cycle. Weekly repayments with interest on the declining
  balance.
- **Bankruptcy** (V3.14, V17.19): triggered at -$1,000,000 company cash, with
  other systems notified through callbacks so this module stays independent of
  employees, subsidiaries and funds. Company failure does not end the
  playthrough (V1.13); refounding requires $500,000 personal net worth.
- **42 further tests** (287 total).

### Fixed

- Owner capital and loan drawdowns were being counted as revenue, which inflated
  profit and would have let a player mistake borrowing for trading well —
  precisely the confusion V17.26 requires the interface to prevent. Financing is
  now a distinct kind of entry that moves cash and appears in cash flow but never
  touches profit. For the same reason, repaying loan principal is financing while
  only the interest is an expense.
- The refounding requirement was never applied to the first replacement company,
  because it tested a history that is only written once the replacement exists.

### Added — Milestone 5: Economy & Banking (V7, V25)

The economy now drives the world. Code lives in `apex_horizon/engine/economy/`
and is documented in [`docs/economy.md`](docs/economy.md).

- **Economic health** (V7.21): a single continuous value in [-1, +1] with the
  five states of V7.4 derived as thresholds over it, keeping the simulation
  deterministic while transitions stay gradual. Health and velocity behave as a
  damped oscillator whose period sets the length of a business cycle.
- **Five states** (V7.4): Growth, Stable, Slowdown, Recession, Recovery. Because
  health alone cannot separate a Slowdown from a Recovery, the state is derived
  from health *and* a smoothed trend, with hysteresis so a reported change always
  means something real.
- **Inflation** (V7.5, V25.2): moves toward a target set by conditions and
  accumulates into a price level, so nominal cash loses meaning over a long
  playthrough.
- **Industry response** (V7.6): every industry has a documented sensitivity —
  defensive industries barely notice the cycle, cyclical ones amplify it.
- **Banking** (V7.10, V25.3): interest rates, lending multiples, and trust
  requirements all follow the economy, so borrowing is cheap and generous in a
  boom and expensive and restrictive in a downturn — hardest exactly when it is
  most needed. Bank tiers make company reputation determine which banks are
  accessible (V33.4). Loans themselves belong to V17.13.
- **Market integration** (V4.4, V4.6, V7.9): economic conditions became a
  distinct, separately reported cause of price movement, industry trends follow
  the economy, and market sentiment leans toward economic health.
- **Project manager decisions recorded** in
  [`docs/design-decisions.md`](docs/design-decisions.md): company founding cost,
  employee capacity per level, bankruptcy thresholds and handling, unlock costs
  to remain data-driven, and the sidebar icon direction.
- **34 further tests** (245 total).

### Fixed

- The economic cycle was noise rather than a cycle: recessions arrived several
  times a year and lasted about three weeks. Because reversion acts on velocity,
  the cycle length is roughly 2*pi/sqrt(mean_reversion) days, so the constant had
  to fall by two orders of magnitude to produce the multi-year downturns V7.19
  describes.
- The state was named from a single day's movement, which reported a Slowdown
  roughly half the time even in a healthy economy; it now uses a smoothed trend.
- Recovery could never occur, because the two directional states were tested
  asymmetrically.
- Economic conditions reached share prices through three channels at once — the
  economy term, sentiment, and industry trends — compounding a sustained boom
  into a market index millions of times its opening level. Industries now
  contribute only their difference from the market average, and sentiment leans
  toward health rather than mirroring it.
- Capped share volatility, which compounds across the hundreds of in-game years
  a save may span and let the most volatile company dominate the index.

### Added — Milestone 4: Market System (V4)

The market now runs. Code lives in `apex_horizon/engine/market/` and is
documented in [`docs/market.md`](docs/market.md).

- **`MarketListing`** (V4.3): price, shares in issue, volatility, performance,
  reputation, financial health, and bounded price history. Market data lives
  here rather than on the company record, so each system owns its own state
  (V15.7) while the game still has only one company structure (V15.4).
- **Cause-by-cause price movement** (V4.4, V4.21): each day's change is the sum
  of company performance, industry conditions, market sentiment, supply and
  demand, and bounded random variation — and the breakdown is kept, so
  `market.explain()` can say *why* a price moved. The total is clamped so no
  combination can produce an implausible overnight jump.
- **Supply and demand** (V4.8): participants register buying or selling
  pressure, scaled by shares in issue so the same order moves a small company
  more than a large one. Pressure is consumed by the price it produces. The
  player's investors and AI companies will use the same entry point (V4.9).
- **Market-wide behaviour** (V4.5, V4.12): sentiment drifts daily with mean
  reversion so bull and bear markets are phases rather than permanent states;
  industry trends and company fundamentals evolve weekly so trajectories are
  recognisable rather than noise.
- **Long-term evolution** (V4.14): companies trading below the floor for a
  sustained period are delisted, and new companies list over time through the
  same world generator, so the market keeps producing fresh opportunities.
- **Statistics** (V4.15): market index, total capitalisation, top movers,
  industry performance, bull/bear state, and historical prices.
- **Determinism and saving** (V4.22, V15.11): every listing's full price history
  is saved, so reloading never produces a different outcome. `update_prices` is
  retry-safe and cannot move prices twice for one day (V15.26).
- **31 further tests** (211 total).

### Fixed

- Rebalanced the daily influence weights, which compounded to absurd growth —
  a 0.4% daily drift is roughly fourfold per year, and produced a
  five-thousand-fold market index across ten in-game years.
- Corrected random variation for compounding. Symmetric multiplicative returns
  are not neutral: a 10% gain followed by a 10% loss leaves you below where you
  started, which dragged the median company down about 70% per decade from
  noise alone. Adding half the variance cancels the drag.

### Added — Milestone 3: World Database & Generation (V32–V36)

The Alternative Earth now exists. Code lives in `apex_horizon/engine/world/` and
is documented in [`docs/world-database.md`](docs/world-database.md).

- **Curated word pools** (V32.2, V32.5): corporate word families including all
  thirteen the Design Bible names explicitly, invented-word fragments,
  internationally representative personal names, city components, and
  institutional vocabulary — all composed into names rather than stored whole,
  giving the "controlled variety" of V32.3.
- **Twenty industry naming identities** (V32.7): every industry in the Design
  Bible's list has a documented naming philosophy and its own nouns and
  patterns, so a player can often infer an industry from a company's name. Four
  identities come from the Design Bible directly; the other sixteen are
  documented here for the first time.
- **`NameGenerator`** (V33, V34.4): composes company, person, city, bank, news
  agency, university, organisation, and fund names, enforcing per-save
  uniqueness across three scopes so a world never contains a company and a bank
  sharing a name. Degrades to a plausible qualifier before ever repeating.
- **World entities** (V30.6): `Company` is the single company structure the
  whole game will use, as V15.4, V26.10 and V12.23 require — AI companies and
  subsidiaries reuse it rather than introducing parallel models.
- **`WorldGenerator`** (V34): builds one save's world — cities, companies with
  industries and named CEOs, banks, news agencies, universities, and regulators
  — dealing industries round-robin so all twenty are represented (V33.3).
  Generation state travels with the world so companies created later never
  collide with the originals.
- **Determinism** (V15.11, V34.6): the same seed regenerates an identical world;
  different seeds produce genuinely different ones (V34.2).
- **62 further tests** (180 total), including data-quality checks on the pools
  themselves and two rules found only by reading real generated output.

### Fixed

- Naming patterns no longer place the industry noun before its qualifier.
  Reversed forms such as "Foods Marigold" and "Masonry Onward" read as generated
  rather than chosen, failing V32.5's professional-tone rule.
- Partnership names no longer repeat a surname ("Gallagher & Gallagher
  Partners"); each placeholder occurrence is now filled independently.
- Removed a non-ASCII entry that had slipped into the invented-word fragments,
  which would have leaked unreadable characters into generated names.

### Added — Milestone 2: Time & Simulation Engine (V13, V29)

The simulation now runs. Code lives in `apex_horizon/engine/simulation/` and is
documented in [`docs/time-and-simulation.md`](docs/time-and-simulation.md).

- **`SimulationClock`** (V13.4, V13.5, V13.29): converts real elapsed time into
  whole in-game days at one second per day, scaled by ×1/×2/×3. Simulation pace
  is fully decoupled from frame rate — polling once a frame and once a second
  give identical results. Pausing banks no time, so unpausing never
  fast-forwards through a popup (V13.20); changing speed never disturbs banked
  time, so rapid switching cannot skip or duplicate ticks (V13.27); and days
  beyond the per-update cap are carried forward rather than dropped, keeping
  long unattended sessions deterministic.
- **`SimulationEngine`** (V15.4): owns in-game time, the seeded generator, and
  the system registry. Systems register phase handlers instead of calling one
  another, staying modular (V15.6, V15.7).
- **Ten ordered daily phases** (V29.2): News, Economy, Banks, Companies,
  Employees, Research, Investment Funds, Market, Financial Calculations, User
  Interface — each completing fully before the next, so no system ever reads
  partially-computed data (V29.13, V29.15). Registration order cannot affect
  execution order.
- **Scheduled progression** (V13.9–V13.11): weekly, monthly, and yearly handlers
  fire on the last day of each completed period, shortest first when several end
  together. Adds `is_last_day_of_week/month/year` to `SimulationDate`.
- **Background updates** (V13.19) roughly every five ticks, and **random event
  rolls** at the configured daily/weekly/monthly/yearly probabilities (V13.18).
  The engine decides only whether an event fires; content arrives with the
  Events database (V33.14).
- **Determinism** (V15.11): a single seeded generator drives every system, and
  saved state includes the generator's internal state so a reloaded world
  continues the same sequence rather than restarting it.
- **Error resilience** (V15.13, V15.26): every handler runs under the retry
  policy, so a failing system cannot end the game — later phases still run and
  time still advances. Handlers must therefore be retry-safe.
- **Shell integration**: the window now advances the simulation each frame and
  displays the live date, with 1/2/3 changing speed (V13.5, V27.9).
- **34 further tests** (119 total), including verification that a 3.5-second run
  advances exactly three in-game days.

### Added — Milestone 1: Data Standards (V30)

Shared value types in `apex_horizon/engine/values/`, enforced through types
rather than developer convention (V30.9), documented in
[`docs/data-standards.md`](docs/data-standards.md).

- **`Money`** (V30.2, V30.7): a single normalised internal currency wrapping
  `Decimal`, so `0.1 + 0.2` is exactly `0.3` and errors cannot compound across
  the hundreds of in-game years a save may span. Full precision is retained
  through every computation; rounding and the `$` symbol occur only at display.
  Money × Money and construction from `bool` both raise.
- **`Percentage`** (V30.3): stored as a fraction (5% is `0.05`, never `5`), with
  the `%` symbol applied only at display, plus `scale_factor()` for applying
  percentage changes.
- **`SimulationDate`** (V30.4, V13.6): in-game time as a single continuously
  incrementing day counter, from which the Year/Month/Week/Day calendar is
  derived — never the reverse. Immutable, with boundary helpers
  (`starts_new_week/month/year`) that will drive the scheduled events of
  V13.9–V13.11. The `Calendar` shape is configuration-driven.
- **`IdAllocator`** (V30.6): sequential per-kind identifiers such as
  `company-000001`, distinct from display names. Sequential rather than random
  so world generation is reproducible (V15.11); counters are saved with the
  world so identifiers never collide after a reload. `new_save_id()` provides
  the random Save ID required by V16.17.
- **Timestamps** (V30.5): ISO 8601 UTC helpers for save metadata, kept strictly
  separate from in-game time; naive datetimes are treated as UTC so an older
  save never fails to load over a missing offset.
- **55 further tests** (85 total), including a direct check of the Design
  Bible's own training example — a Friday plus ten days lands on a Monday.

Open interpretation, pending project manager confirmation: the Design Bible
states seven-day weeks but not weeks per month or months per year. Uniform
4-week months (28-day months, 336-day years) were chosen so weeks nest cleanly
inside months as the V13.6 display format implies. The values live in
`config/gameplay.toml`, so revising them is a configuration change.

### Added — Milestone 0: Foundation

- **Layer-based project structure** (V15.3): `apex_horizon/engine/` for
  simulation systems, `apex_horizon/ui/` for the presentation layer, plus
  top-level `config/`, `assets/`, `docs/`, and `tests/`.
- **Centralised gameplay configuration** (V15.10, V1.22): `config/gameplay.toml`
  holds every tunable value, each annotated with the Design Bible section it
  derives from. `apex_horizon/engine/config.py` provides typed, dotted-path
  access and fails loudly on missing or mistyped values.
- **Path resolution** (`engine/paths.py`): resolves bundled data (config,
  assets) and player-writable data (saves, logs) for both source runs and
  future PyInstaller builds.
- **Logging** (V15.12): rotating log file plus console output, capped at ~5 MB
  total. Logging failures degrade to console only rather than blocking play.
- **Error handling** (V15.13): `run_with_retry` implements the required policy —
  attempt, retry, retry again, then log the full traceback, notify the player,
  and ask them to report the issue. Failures return a result object instead of
  raising so gameplay can continue.
- **Application shell** (`ui/window.py`): a minimal window and frame loop so the
  mandatory "the game launches successfully" check (V15.19, V19.10) is
  verifiable from Milestone 0 onward. Placeholder pending the UI framework.
- **Test suite**: 30 tests covering configuration, logging, paths, the retry
  policy, and a headless launch test of the real window.
- **Tooling**: `pygame-ce` runtime dependency; explicit Ruff rule selection
  pinned in `pyproject.toml` so a future Ruff release cannot change the lint
  surface underneath CI (V19.11).

### Project manager decisions

Values the Design Bible deliberately left undefined, supplied by the project
manager on 2026-08-08 and recorded in `config/gameplay.toml`:

- Company bankruptcy occurs at **−$1,000,000** company cash (V3.20, V17.25).
- Founding a company costs **$25,000** of personal cash; the same figure gates
  re-founding after a bankruptcy (V3.3).
- Audio will reuse the legacy prototype's cues for now (the Design Bible does
  not specify audio).
- The Design Bible PDF lives in `docs/` locally and is deliberately not
  committed to the repository.
