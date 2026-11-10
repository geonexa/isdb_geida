# Introduction

## What GEIDA is

GEIDA (Geoinformatics Data Platform) is the Islamic Development Bank's web platform for
using geospatial data in project work. It answers the questions IsDB staff ask at each
stage of a project:

- **Where** is the project, and what is in its area of influence?
- **What** do open data say about that area: schools, health facilities, roads,
  buildings, rainfall, land cover, terrain?
- **How** do those facts relate to the indicators the project committed to in its
  Results Framework?

GEIDA is phase II of IsDB's Earth observation work. Phase I was the
[EO Toolkit](https://etoolkit.terrawatch.net/), a set of guides and training material;
GEIDA turns that guidance into a working platform.

## Principles

| Principle | What it means in practice |
|---|---|
| **The project cycle is the spine** | Every analysis belongs to a project phase (PCN → PPER), and its results flow to the project's indicators. |
| **Evidence, not automatic values** | An analysis proposes evidence. A person accepts or rejects it; nothing is written into a Results Framework on its own. |
| **Honest about data** | An analysis runs only where its data exist, and says so when they don't. Every result names its source and snapshot date. |
| **Data are data** | CRI codes, analysis modules and country lists are loaded from files, never hard-coded, so IsDB can revise them without a code change. |
| **Portable to IsDB hosting** | Runs on a single server built from open-source components. External services (tile server, open-data hosts) can be replaced by copies on IsDB servers. |

## The main areas of the platform

| Area | Path | For |
|---|---|---|
| **Home and content pages** | `/`, `/<section>` | Everyone: what GEIDA does, the Knowledge Hub, training links |
| **Projects** | `/projects` | Project teams: onboarding, Results Framework, review |
| **Project workspace** | `/projects/<code>` | Project teams: map, analyses and data layers, evidence, documents, map export |
| **Data Catalog (Geo-Portal)** | `/geoportal` | Everyone: browse raster and vector layers for any member country, draw areas, download clipped data |
| **Analytics** | `/analytics` | Analysts: full GIS workspace (layers, styling, processing, models) |
| **Admin** | `/admin` | Administrators: users, groups, reference data |

See [Features](features.md) for each area in detail and [Users and roles](roles.md) for
who can do what.

## Partners

| Organisation | Role |
|---|---|
| Islamic Development Bank (IsDB) | Owner; project data; future hosting by IMDT (IsDB IT) |
| Terra, Expo City Dubai | Design and development |

## Where to go next

- [The IsDB project cycle](project-cycle.md): how GEIDA maps onto PCN, PPRR, PAD, PIASR, PCR and PPER.
- [Architecture](../architecture/index.md): how the system is built.
- [Glossary](glossary.md): the abbreviations used throughout these pages.
