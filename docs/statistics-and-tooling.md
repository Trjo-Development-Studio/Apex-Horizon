# Statistics & Developer Tooling

Covers Design Bible **Volume 28** (statistics) and **V15.18** (developer
commands). Code lives in `apex_horizon/engine/statistics/`,
`apex_horizon/debug/` and `apex_horizon/ui/console.py`, with the page in
`apex_horizon/ui/pages/statistics.py`.

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

V15.18 asks for developer commands covering money, time, employees, research,
market events and the economy, run from the terminal that launched the game
rather than from an in-game menu. All six exist, plus unlocks, status and help.

The project manager then asked for the same commands **inside the window**, on
**Ctrl+T** — a terminal is not available to a packaged build or to anyone who
launched the game from a shortcut. Both surfaces drive one object,
`debug/commands.py`, so a command cannot exist in one and not the other and the
help text is the same text.

    apex_horizon/debug/commands.py   what every command means and does
    apex_horizon/debug/console.py    the terminal reader (V15.18)
    apex_horizon/ui/console.py       the in-game overlay (Ctrl+T)

The overlay owns no commands and knows nothing about money, time or unlocks: it
reads keys and hands whole lines over. It executes nothing from the operating
system — the parser understands the commands below and refuses everything else.

### The commands

    money player                            time
    money player set|add|remove {amount}    time set {year} {month} {week} {day}
    money company                           time add {amount}{year|month|week|day}
    money company set|add|remove {amount}   time cancel

    unlocks                                 help
    unlock add {unlock_name}                help money
    unlock remove {unlock_name}             help time
    unlock add all                          help unlocks

`hire`, `research`, `event`, `economy` and `status` remain from V15.18.

### They act on the real game

`money player add 1000` moves the same cash the market spends, the interface
draws and the save writes. Company money goes through the company's own transfer
methods so the ledger and cash-flow statement stay truthful about where it came
from (V17.26) — the console skips the *price*, which is its purpose, not the
bookkeeping. `unlock add` goes through the Unlock Tree and re-applies
`UnlockEffects`, so what it grants actually changes the game rather than being
recorded and ignored.

**Unlocks stay a valid tree.** V6.9 makes progression sequential, so granting a
deep unlock also grants what it requires, and removing one also removes anything
built on top of it. Both say what they had to take with them. The unlock every
player starts with (V6.4) cannot be removed, because a save would restore it
anyway.

**Time only moves forwards.** The engine knows how to live a day, not to unlive
one, so `time set` to a past date is refused with a sentence rather than
half-rewound into a state the simulation never produces.

**Long jumps are spread across frames.** Simulating a year honestly takes a few
seconds, so `time add 5year` would freeze the window for half a minute if it ran
inside one command. Instead the command schedules the days and the application
advances a slice of them each frame (`debug.fast_forward_budget_ms`), with the
console header counting down and the game still drawing. `time cancel` abandons
a jump; anything longer than `debug.max_fast_forward_years` is refused as a
typo.

### Behaviour

**The console pauses the simulation while it is open**, exactly as a popup does
(V13.20): state being read should not move underneath the reader. A scheduled
time jump still advances, because that was asked for explicitly.

**It captures the keyboard.** While open it consumes every event, so the speed
shortcuts and page navigation cannot fire underneath what is being typed, and
the Ctrl+T that opened it does not type a `t`.

**Commands are shown apart from their output**: what was typed appears in the
accent colour behind a `>`, answers in plain text, refusals in red. It is
available in a running game, not on the Start Menu, where there is no world to
change.

**The terminal reader is inert without a terminal.** Tests, CI, and a windowed
launch with no console all leave stdin unusable, and it simply does not start; a
test asserts this, because a debug tool that blocked CI would be worse than no
debug tool. The in-game console always works.

**Nothing typed can end the game.** Unknown commands, bad arguments, wrong
arity, absurd numbers and 500-character nonsense are all reported and swallowed;
a parametrised test fires a list of malformed input at it and checks the
simulation is still standing afterwards.

    > money player add 1000
    Personal cash: $11,000.00 (was $10,000.00).
    > unlock add better_analytics_2
    Unlocked Better Analytics 2, and what it required: Basic Analytics, Better Analytics 1.
    > time add 5year
    Simulating 1,680 in-game day(s). The game keeps running while it catches up.
    Time is now Year 6, Month 1, Week 1, Day 1.
    > teleport
    Unknown command: teleport. Use 'help' for available commands.
