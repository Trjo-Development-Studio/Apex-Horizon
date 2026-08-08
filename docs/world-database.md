# World Database & Generation

Implements Design Bible Volumes 32–36. Code lives in `apex_horizon/engine/world/`.

Volume 36 sets the division of responsibility: **the Design Bible defines the
standards; the implementation generates the content.** Everything below is
generated against the standards, never invented alongside them.

## Why curated pools rather than random strings (V32.2, V32.3)

Randomness alone produces unpredictability, not believability. Names are
therefore composed from curated word pools using per-industry patterns —
"controlled variety": a wide enough range that repetition is never noticeable,
from standards narrow enough that every result still belongs to the same
universe. The player should never be able to tell a generated name from a
handcrafted one (V32.4).

## Naming standards (V32.5)

Every generated name aims to be readable at a glance, pronounceable, memorable,
professional in tone, international in flavour, and free of joke names, real
brands, offensive meanings, and meaningless letter combinations.

Two rules proved to need explicit enforcement, both verified by tests:

- **The qualifier always precedes the industry noun.** Reversed forms such as
  *"Foods Marigold"* or *"Masonry Onward"* read as generated rather than chosen.
- **Partnership names never repeat a surname** — *"Gallagher & Gallagher
  Partners"* fails the same test.

A further test asserts every pool entry is plain ASCII, non-empty, trimmed, and
free of duplicates.

### Corporate word families (V32.8)

Unrelated companies may share corporate words — real corporate naming echoes
itself across industries, and reuse signals that these companies inhabit one
shared linguistic world. The thirteen words the Design Bible lists explicitly
(Horizon, Atlas, Summit, Meridian, …) are present, alongside others in the same
register. No word family is any company's exclusive property.

### Industry identities (V32.7)

All twenty industries have a documented naming philosophy, so a player can often
infer an industry from a name alone. The Design Bible states four directly —
Technology (short, modern, invented), Financial (solid, trust-projecting),
Healthcare (clarity and reassurance), Entertainment (personality and flair). The
other sixteen are documented in `industries.py`, written to sit consistently
alongside those four.

Sample output:

| Industry | Examples |
|---|---|
| Technology | Dyntec Systems · Caleon · Cascade Technologies |
| Financial | Eriksen & Costa Investments · Summit Wealth |
| Food | Providence Bakeries · Blomqvist Foods |
| Mining | Equinox Minerals · Zenith Quarries |
| Hospitality | Tidewater Resorts · Cascade Hotels |

## Database categories (V33)

V33.2 requires every category to be documented against the same six properties.

| Category | Purpose | Scale | Duplicate prevention | Diversity | Future scalability |
|---|---|---|---|---|---|
| **Companies** | Populate the Market (V4); pool for subsidiaries (V12) and AI companies (V26) | Pool far exceeds one playthrough | Unique per save | Even spread across all 20 industries | New industries addable without touching existing entries |
| **Banks** | Provide loans (V17.13) | Modest, stable pool | Unique per save | Varying size/reputation tiers | Ready for multi-currency (V17.20) |
| **CEOs** | Give companies a human face for news (V10.5) | ~1 per company | Unique per save | Internationally representative | Extendable to executive employees (V18.24) |
| **Employees** | Applicant pools (V5.3, V6.7.5) | Largest category | Unique where practical (V33.6) | No two applicants feel interchangeable | Supports future specialisations |
| **Cities** | Geographic texture (V24) | Moderate, fixed | Unique per save | Varied roots and suffixes | Ready for a future map system |
| **Universities** | News texture; future employee backgrounds | Small, stable | Unique per save | Tied to generated cities | Independent of other systems |
| **Investment Funds** | Name player and AI funds (V11.6) | Large, renewable | Unique per save | Distinct across many funds | Supports future fund types (V11.16) |
| **News Agencies** | A byline for news (V10) | Small, fixed | Unique per save | Mix of general and financial outlets | Ready for outlet reputation/bias |
| **Organisations** | Regulators and industry bodies (V24.4) | Small, stable | Unique per save | Spread across regulation, policy, oversight | Independent of any future government sim |

**Deferred, deliberately.** Products (V33.12), Achievements (V33.13), and Events
(V33.14) are architected in the Design Bible but not generated yet: Products and
Events belong with the systems that use them, and Achievements are *authored*
rather than generated (V33.13, V35.8). V33.17 is explicit that structure
precedes content.

### Uniqueness scopes

Names are unique within three scopes rather than per category, so a world never
contains a company and a bank sharing a name:

- `organisation` — companies, banks, news agencies, universities, organisations, funds
- `person` — CEOs and employees (one shared population, V33.6)
- `city` — places

If a pool ever fails to yield an unused name, the generator degrades to a
plausible qualifier ("… Group", "… International") and only then to a numeric
suffix — never a duplicate, never an infinite loop.

## World generation (V34)

Generation runs **once, at save creation**; from then on the Deterministic
Simulation guarantee (V15.11) takes over and the world must reload identically
(V34.6).

- **Every save feels unique** (V34.2): the databases are a shared pool each save
  draws its own combination from, not a fixed roster.
- **Even industry coverage** (V33.3): industries are dealt round-robin, then
  shuffled, so all twenty appear and which ones receive the remainder varies by
  save.
- **Generation state is saved.** The `IdAllocator` counters and the name
  generator's used-name sets travel with the world, so companies created later
  in a playthrough never collide with ones generated at the start.

```python
world, allocator, names = generate_world(seed)
```

## Dynamic content (V35)

Content created *during* play — fund names when a fund is founded (V35.6), and
later news headlines and company announcements — draws from these same standards
at the moment of creation. V35.10 is the binding rule: dynamic content must never
contradict the static databases, so a headline can never name a company that does
not exist.
