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

## Planned documents

One document per major system, added as each is implemented (V15.14, V19.13):
Time & Simulation, Market, Economy, Company, Employees, Investment, Research &
Analytics, News, Unlock Tree, Save System, Financial Management, Acquisitions,
Investment Funds, AI Companies, and the World Database.
