# Statistics & Developer Tooling

Covers Design Bible **Volume 28** (statistics) and **V15.18** (terminal debug
commands). Code lives in `apex_horizon/engine/statistics/` and
`apex_horizon/debug/`, with the page in `apex_horizon/ui/pages/statistics.py`.

---

## Statistics

V28 is a catalogue volume: it consolidates figures introduced across earlier
volumes and explains why each exists. Most of it therefore already existed —
company statistics on the Company page, employee statistics on theirs, fund
statistics from Volume 11, and so on. The Statistics page gathers the categories
in one place.

**V28.7 lifetime statistics** were genuinely new, and are the reason the page is
worth having: cumulative figures across an entire playthrough, kept as
**permanent, never-reset records**.

That "never reset" is what makes them different from every other number in the
game. A company can go bankrupt and be founded again (V1.3); its ledger starts
over, its staff are released, its subsidiaries are gone. None of that touches
these counters, because they describe the *playthrough*, not the company. A test
pins exactly this: hires from a lost company still count.

V28.8 sets the bar for what belongs — "every statistic should answer a question
the player would actually ask" — so these count things a player would say out
loud: how much I ever made, how many people I ever employed, how many companies
I ever bought.

### How they are fed

Nothing in the engine knows the statistics module exists. Counters attach to the
callback lists systems already expose — `on_hire`, `on_acquired`, `on_created`,
`on_trade`, `on_invested`, `on_closed`, `on_fee`, `on_bankruptcy`, `on_unlocked`
— which is the same pattern used for bankruptcy and news (V15.7).

Worth recording: the counters were defined before they were connected, and the
page showed *Profit ever made $0* next to *Realised $3,598,463*. Building the
page is what exposed it. A recorder that nothing calls is invisible in tests
that only exercise the recorder.

---

## The developer console (V15.18)

V15.18 asks for developer commands run from the terminal that launched the game,
rather than an in-game menu, covering money, time, employees, research, market
events and the economy. All six exist, plus `unlock`, `status` and `help`.

**Threading.** Reading a line from a terminal blocks until return is pressed,
which would freeze the simulation, so a daemon thread reads and queues whole
lines. The application drains that queue once a frame and runs commands on its
own thread — a command therefore never mutates the world halfway through a frame
that is being drawn.

**It is inert without a terminal.** Tests, CI, and a windowed launch with no
console all leave stdin unusable, and the console simply does not start. A test
asserts this, because a debug tool that blocks CI would be worse than no debug
tool.

**A typo must never end the game.** Unknown commands, bad arguments and wrong
arity are all reported and swallowed; the simulation carries on.

    > status
    Day 1 (Year 1, Month 1, Week 1, Day 1)
    > money 50000
    Personal cash is now $60,000.
    > unlock all
    Granted every unlock.
    > event up 3
    Moved 63 listings by +3.0%.
