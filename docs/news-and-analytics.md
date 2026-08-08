# News & Analytics

Covers Design Bible **Volume 10 (News System)** and **Volume 9 (Research &
Analytics)**. Both are read-only layers over the simulation: the News System
reports what happened, and the Analytics layer arranges what exists. Neither
invents an event.

Code lives in `apex_horizon/engine/news/` and `apex_horizon/engine/analytics/`,
with their pages in `apex_horizon/ui/pages/news.py` and
`apex_horizon/ui/pages/analytics.py`.

---

## News (V10)

### Where it runs

News is **step 1 of the simulation day** (V29.3), and deliberately reports on
*yesterday's* settled outcomes. Running first, over data that has already
settled, is what guarantees a headline always describes something that genuinely
happened (V10.9, V10.24) rather than something the day is still deciding.

Like every phase handler it guards against being run twice for the same day
(V15.26) via `_last_generated_day`.

### What gets reported

| Kind | Trigger | Bible |
|---|---|---|
| Company | A daily price move of at least `news.company_move_threshold` (4.5%) | V10.5, V10.8 |
| Breaking | A move of at least `news.breaking_move_threshold` (12%) | V10.13 |
| Market | Every `news.market_report_interval` days (7): strongest and weakest industry, the index, the mood | V10.6 |
| Economic | When the economy changes state | V10.7 |

Headlines are drawn from families of templates rather than single strings, so
the same kind of event does not produce a word-for-word identical article
(V10.9). The template supplies the direction, so the figure is written without
its sign — "slides 4.9%", never "slides -4.9%".

Every article carries a byline from one of the world's own news agencies
(V33.10); non-basic tiers prefer an agency that specialises in finance.

### Tiers

`NewsTier` — Basic, Market, Economic, Breaking — is raised through the News
branch of the Unlock Tree (V6.6.2, V10.4). A locked tier is genuinely withheld:
without the Breaking unlock the player does not see the biggest stories at all
(V10.16), rather than seeing them stripped of detail.

### News moves prices

A story pushes the price of the company it concerns, in the same direction, for
a few days (V10.10). The push is `impact × news.impact_strength`, decaying by
`news.impact_decay` each day and dropped once negligible.

V4.4 lists news as one of the causes of a price change, so `PriceChange` carries
a **separate `news` term** rather than folding it into sentiment. That is what
lets the market tell the player a move was caused by the news (V4.21).

### The archive

The last `news.archive_size` (120) articles are kept and remain readable on the
News page (V10.15) — an archive, not a ticker. The page filters by tier, offering
only tiers actually unlocked.

**Notifications are reserved.** The world publishes something most days, and
pushing every routine company move as a toast buries the screen and makes the
one story that mattered no easier to notice. Only breaking news and shifts in
the economy interrupt (V10.14, V14.16); everything else waits on the page.

---

## Analytics (V9)

### Separation

V9.22 requires analysis to be separated from the simulation, and it is: nothing
in `analytics/` computes a value the simulation depends on. Reports are plain
data (`Report` of `Metric`) that the page renders without knowing how any figure
was arrived at.

### The five views

`AnalyticsService` builds one report each for the company (V9.5), its employees
(V9.6), the market (V9.7), investments (V9.8), and change over time (V9.10). A
report whose subject does not exist yet — no company, no history — returns
`None` and is simply absent, because V9.21 prefers showing nothing to showing a
figure the player cannot act on.

### Tiers

`AnalyticsTier` — Basic, Detailed, Advanced — gates depth, not access. Basic
answers *what is happening*; each level above adds the kind of question a player
only starts asking once they have a reason to.

| Tier | Company report adds |
|---|---|
| Basic | Cash, profit this week |
| Detailed | Profit margin, net worth |
| Advanced | Lifetime profit |

### History

Nothing else in the simulation remembers the past — the market keeps prices, but
wealth and cash exist only as their current value. `HistoryRecorder` takes a
snapshot on each **month boundary** (V13.10) of net worth, cash, company cash
and the market index. A century of play is about 1,200 rows, capped by
`analytics.history_limit`.

`change_over()` returns `None` rather than a misleading number when there is not
enough history to answer.

---

## Determinism note

Both systems are saved in full (V16.11). Adding news exposed a latent
determinism defect worth recording: the **world generator's and name
generator's random streams were not part of the save**, so a company founded
after loading differed from the one an uninterrupted game would have founded.
Both now carry their stream position, restoring the guarantee of V15.11 — a
reloaded game continues the same random sequence rather than restarting it.
