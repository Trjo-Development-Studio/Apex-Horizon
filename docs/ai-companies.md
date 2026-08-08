# AI Companies

Covers Design Bible **Volume 26**, together with the AI behaviour V26 collects
from V4.9, V5.18, V7.13, V8.16, V17.18 and V18.16. Code lives in
`apex_horizon/engine/ai/`.

V26.1 is unusually direct about what this volume is: it *documents* existing
behaviour rather than introducing new mechanics. That shaped the implementation
more than anything else — almost nothing here is new machinery.

---

## There is no AI company class

V26.10 requires AI companies to be instances of the **same underlying structure**
as the player's own, differing only in that their strategic decisions are
generated procedurally. So they are:

```
InvestmentCompany  ←  the player owns one
                   ←  each AI company is another
```

The class was called `PlayerCompany` until this milestone. It was renamed
because it is no longer the player's alone, and a name that implied otherwise
would have been the first thing to mislead someone reading the code.

What differs is only the decision-maker. `AIDirector` makes the calls a player
would make — when to hire, into which department, when the organisation has
grown enough to expand. Everything else is not written in this package at all,
because it already exists:

| Behaviour | Where it actually happens |
|---|---|
| Investing | The V8.3 workflow, unchanged (V26.7) |
| Market impact | Ordinary recorded demand (V26.8, V4.8) |
| Salaries, costs, solvency | The same financial rules (V17.18) |
| Employees | The same roster and hidden characteristics (V5.18) |

That reuse is the requirement, not a shortcut: V26.10 asks for it so AI
companies stay automatically compatible with every future change to
company-level systems (V15.7).

---

## Why no two behave alike

V26.3 puts the source of variety in the *employees*, not in the director. An AI
company's behaviour comes from the hidden characteristics of whoever it hired —
investment size, risk tolerance, style, market focus (V5.7) — exactly as the
player's company does.

V26.4 asks for AI staff to skew toward higher risk **on average**. That is done
by biasing the draw, not by forcing it:

* Each AI company draws its own `risk_bias` between `ai.risk_bias_minimum` and
  `ai.risk_bias_maximum`.
* The bias shifts the risk-tolerance distribution upward when generating an
  applicant.
* Cautious employees still appear at any bias — a test pins this — so some AI
  companies end up conservative simply through who they happened to hire, which
  is what V26.3 requires.

The result is V26.11's population: some cautious, some reckless, some thriving,
some failing. Measured over 15 in-game years, the strongest firm reached $2.8M
while the weakest sat below zero.

---

## Growth

The player raises Company Level by buying unlocks (V6.7.3). An AI company has no
Unlock Tree, so the same progression is reached from what the company is worth,
against `ai.level_value_thresholds`. V26.5 wants growth to be an emergent
outcome of workforce and risk rather than a scripted plan, and tying it to value
is what delivers that: a company that invests well grows and can employ more
people; one that does not stays small.

Acquisitions (V12.14) and investment funds (V11) are the other growth routes
V26.5 names. Both arrive with those volumes; AI companies will pick them up
automatically, because they are ordinary companies.

---

## Competition

V26.6 is explicit that competition is **never adversarial in a scripted sense**.
No AI company knows the player exists. They simply act, and because they act
continuously (V13.15), an opportunity the player hesitates over may be taken
first. That is the whole of the competition, and it follows from Market
Independence (V4.10) rather than from any targeting logic.

Their aggregate buying and selling is a real component of supply and demand
(V26.8) — with twelve companies trading daily, the market moves because other
people are in it.

---

## Determinism

Each director owns a random stream, and its state is saved. This is the third
time this class of bug has appeared in the project (after the world generator
and the name generator), and it fails the same way each time: the stream
restarts on load, the AI takes different decisions, its orders reach the market
differently, and a reloaded world quietly diverges from the saved one (V15.11,
V16.28).

**Any new system that draws randomness and affects the world must save its
stream position.**

---

## Performance

Twelve AI companies, each with staff running the full investment workflow, cost
about 17 ms of simulated day — comfortably inside the frame budget at every
speed the game offers.

Adding them exposed an unrelated bottleneck worth recording: save obfuscation
XOR'd payloads a byte at a time in Python, which made autosaving the single most
expensive thing the simulation did — more than every company in the world
combined. It now works a machine word at a time (about 24 ms per megabyte),
which roughly halved the cost of running a year.
