# Apex Horizon — Technical Documentation

Design Bible V15.14 requires major systems to carry technical documentation
explaining their responsibilities, architecture, and important implementation
details. This directory holds that documentation; it grows alongside the
codebase (V19.13).

## Source of truth

The **Apex Horizon 2.0 Design Bible (Definitive Edition)** is the authoritative
specification for all gameplay design. By project manager decision it is kept in
this directory locally but is **not committed** to the repository (see
`.gitignore`). Nothing in these documents overrides the Design Bible; where the
two disagree, the Design Bible wins (V19.3).

## Documents

| Document | Covers |
|---|---|
| [architecture.md](architecture.md) | Layer structure, engine foundations, and the planned simulation architecture |
| [data-standards.md](data-standards.md) | The shared `Money`, `Percentage`, `SimulationDate`, and identifier types (V30) |
| [time-and-simulation.md](time-and-simulation.md) | The clock, the simulation engine, and the ten daily phases (V13, V29) |
| [world-database.md](world-database.md) | Naming standards, database categories, and world generation (V32–36) |
| [market.md](market.md) | Share prices, supply and demand, sentiment, and market evolution (V4) |
| [economy.md](economy.md) | Economic states, inflation, industry response, and lending conditions (V7, V25) |
| [company-and-finances.md](company-and-finances.md) | The player's company, the ledger, loans, and bankruptcy (V3, V17) |
| [save-system.md](save-system.md) | Save format, slots, validation, recovery, migration (V16) |
| [user-interface.md](user-interface.md) | The interface framework: theme, widgets, pages, popups (V14, V27) |
| [design-decisions.md](design-decisions.md) | Project-manager rulings where the Design Bible is deliberately silent |

## Planned documents

One document per major system, added as each is implemented (V15.14, V19.13):
Time & Simulation, Market, Economy, Company, Employees, Investment, Research &
Analytics, News, Unlock Tree, Save System, Financial Management, Acquisitions,
Investment Funds, AI Companies, and the World Database.
