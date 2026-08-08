# Time & Simulation

Implements Design Bible Volume 13 (Time & Simulation System) and Volume 29
(Simulation Order). Code lives in `apex_horizon/engine/simulation/`.

## The clock (`clock.py`)

`SimulationClock` converts real elapsed time into **whole in-game days**. The
default pace is one real second per in-game day (V13.4), scaled by the player's
chosen speed of ×1, ×2 or ×3 (V13.5).

Because the clock accumulates real time and only ever reports whole days,
simulation pace is completely decoupled from render frame rate (V13.29) —
polling it sixty times a second and once a second produce identical results.

Three behaviours are worth knowing:

- **Pausing banks nothing.** While paused, time is neither accumulated nor
  released, so unpausing never fast-forwards through the time a popup was open
  (V13.20). The clock provides the mechanism; *deciding* when to pause belongs to
  the interface, since only popups may pause the simulation.
- **Speed changes never disturb banked time** (V13.27). Switching speed changes
  only the rate the accumulator fills, so rapid switching can neither skip nor
  duplicate a tick.
- **Long idles are capped, not dropped.** Days beyond `max_days_per_update` are
  *retained* and released over following frames. A long unattended session
  therefore stays deterministic (V13.27) while no single frame blocks the
  interface.

## The engine (`engine.py`)

`SimulationEngine` owns in-game time, the seeded random generator, and the
registry of systems. Systems never call one another through it; they register
handlers and receive a `SimulationContext` describing the day being processed
(V15.6, V15.7):

```python
engine.register(SimulationPhase.MARKET, update_share_prices)
engine.register_boundary(PeriodBoundary.MONTH, pay_salaries)
```

### Daily phase order (V29.2)

Each day runs these ten phases, strictly in order, each completing fully before
the next begins (V29.15):

1. News · 2. Economy · 3. Banks · 4. Companies · 5. Employees · 6. Research ·
7. Investment Funds · 8. Market · 9. Financial Calculations · 10. User Interface

The order guarantees every system reads only fully-settled data from the systems
before it (V29.13). Registration order is irrelevant — the engine sorts by the
phase definition, so a system cannot accidentally run early by being registered
first.

### Scheduled progression (V13.9–V13.11)

Weekly, monthly, and yearly handlers fire on the **last day of each period**,
after that day's phases have settled, because V13.9 ties weekly events to
*completed* weeks. When several periods end on the same day the handlers run
shortest-first: week, then month, then year.

With the current calendar that means weekly events on days 7, 14, 21, 28…,
monthly events on day 28 and every 28 days after, and yearly events on day 336.

### Background updates (V13.19)

Handlers registered with `register_background` run roughly every five ticks.

### Random events (V13.18)

The engine rolls for a random event at each time scale using the configured
probabilities — daily 5%, weekly 25%, monthly 35%, yearly 35%. It decides only
*whether* an event occurs; what actually happens comes from the systems that
register handlers, drawing on the Events database of V33.14. No roll is made when
nothing is listening, so the random sequence stays stable regardless of which
systems happen to be present.

## Determinism (V15.11)

A single seeded generator drives every system, and the engine's `state()`
includes both the seed and the generator's internal state, so a reloaded world
continues the same sequence rather than restarting it. The test suite verifies
that the same seed reproduces an identical sequence, that different seeds
diverge, and that a save/restore round trip resumes exactly where it left off.

Systems must draw randomness from `context.rng` rather than the global `random`
module, or determinism is lost.

## Error resilience (V15.13, V15.26)

Every handler runs under the retry policy, so a failing system cannot end the
game: later phases still run, time still advances, and the player is notified
once retries are exhausted.

**Handlers must therefore be retry-safe.** A handler that fails partway may be
invoked again for the same day, so changes should be applied atomically or be
safe to repeat.

## Driving the engine

The application shell advances the simulation once per frame and reads state for
display only, keeping game logic out of the interface layer (V15.5):

```python
delta_ms = clock.tick(TARGET_FPS)
engine.update(delta_ms / 1000.0)
```

`run_days(n)` advances time immediately, ignoring the clock. It exists for tests
and for the terminal debug commands of V15.18, which are deliberately thin
wrappers around ordinary simulation APIs rather than special-cased bypasses
(V15.28).
