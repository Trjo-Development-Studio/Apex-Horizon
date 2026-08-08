# Data Standards

Implements Design Bible Volume 30. These shared value types live in
`apex_horizon/engine/values/` and are used by **every** gameplay system. V30.9
requires the standards to be enforced through types rather than developer
convention, so that a value can never be misinterpreted or rounded differently
as it crosses between systems.

## Money (V30.2, V30.7)

All monetary values — personal cash, company cash, investment amounts, fund
capital — use a single normalised internal currency. The `$` symbol is applied
only at display.

`Money` wraps `Decimal`, not `float`. Binary floating point cannot represent
ordinary decimal amounts exactly, and those errors compound across the hundreds
of in-game years a save may span (V28.7):

```python
Money("0.1") + Money("0.2") == Money("0.3")   # exact
```

Full precision is retained through every computation; **rounding happens only in
`format()`** (V30.7):

```python
money = Money("10.005")
money.format()   # "$10.01"  — display only
money.amount     # Decimal("10.005") — unchanged
```

Supported operations: `+` and `-` between `Money`; `*` by a number or
`Percentage`; `/` by a number (→ `Money`) or by `Money` (→ ratio). Multiplying
money by money raises — it is meaningless. Constructing from `bool` raises,
since `bool` subclasses `int` and would almost always be a mistake.

Because a future multiple-currency system is a presentation-layer concern
(V17.20), no system should ever store a currency alongside an amount.

## Percentage (V30.3)

Percentages are stored as **fractions**: 5% is `0.05`, never `5`. The `%` symbol
is applied at display only.

```python
rate = Percentage.from_percent(5)   # fraction == 0.05
rate.as_percent                     # Decimal("5")
Money(200) * rate                   # Money("10")
rate.scale_factor()                 # Decimal("1.05") — for applying a change
```

## SimulationDate (V30.4, V13.6)

In-game time is a **single continuously incrementing day counter**. The
Year / Month / Week / Day calendar is *derived* from it, never the reverse —
this makes Continuous Simulation (V13.7) a structural guarantee rather than a
display convention.

```python
date = SimulationDate(1)            # day 1 of a playthrough
date.label()                        # "Year 1, Month 1, Week 1, Day 1"
date.advanced(10).weekday_name()    # dates are immutable
SimulationDate(15) - SimulationDate(10)   # 5 (elapsed days)
```

Boundary helpers drive the scheduled events of V13.9–V13.11:
`starts_new_week()`, `starts_new_month()`, `starts_new_year()`.

### Calendar shape

Loaded from `config/gameplay.toml` (V15.10), currently 7-day weeks, 4-week
months, 12-month years — so 28-day months and 336-day years.

Seven-day weeks are established by the training example in V5.9/V13.12
("beginning on a Friday for 10 days completes the following Monday"), which the
test suite verifies directly. **The Design Bible does not state weeks per month
or months per year.** Uniform 4-week months were chosen so weeks nest cleanly
inside months, as the V13.6 display format implies. Because the values are
configuration, changing them later is a one-line edit plus a save migration.
*Pending confirmation from the project manager.*

Day 1 of a playthrough is defined as a Monday; the Design Bible does not specify
a starting weekday.

## Identifiers (V30.6)

Every persistent entity receives a unique internal identifier at creation, kept
distinct from its display name so entities can be renamed and cross-referenced
without ambiguity.

```python
allocator = IdAllocator()
allocator.next_id(EntityKind.COMPANY)   # "company-000001"
```

Identifiers are **sequential, not random**, so replaying the same world
generation produces the same identifiers — supporting the Deterministic
Simulation guarantee (V15.11). The allocator's counters are saved with the world
(`state()` / `from_state()`) so identifiers never collide after a reload. One
allocator belongs to one save, consistent with Independent Worlds (V16.12).

`new_save_id()` is the exception: the Save ID (V16.17) is a random UUID because
it must be globally unique across a player's machine and future cloud saves. It
is generated once at save creation and never during simulation, so it does not
affect determinism.

## Timestamps (V30.5)

Real-world timestamps for save metadata (V16.16) are kept strictly separate from
in-game time, and use ISO 8601 in UTC — sortable as text, explicit offset,
locale-independent. Naive datetimes are assumed to be UTC rather than rejected,
so an older save can never fail to load over a missing offset (V16.15).
