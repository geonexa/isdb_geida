---
hide:
  - navigation
  - toc
---

<div class="geida-hero" markdown>

# GEIDA — IsDB Geoinformatics Data Platform

<p class="lead">GEIDA brings Earth observation and open geospatial data into the Islamic
Development Bank's project cycle. Staff register a project and its area of influence,
link its Results Framework to IsDB Core Result Indicators (CRIs), and run curated
analyses whose results become reviewable evidence for those indicators, from the
concept note (PCN) to post-evaluation (PPER).</p>

</div>

<div class="grid cards" markdown>

-   :material-book-open-variant:{ .lg .middle } **Introduction**

    ---

    What GEIDA is, who uses it, and how it follows the IsDB project cycle.

    [:octicons-arrow-right-24: Read the introduction](introduction/index.md)

-   :material-sitemap:{ .lg .middle } **Architecture**

    ---

    Components, data flow, data sources and the analysis-module engine.

    [:octicons-arrow-right-24: See the architecture](architecture/index.md)

-   :material-laptop:{ .lg .middle } **Setup**

    ---

    Run GEIDA on your machine: conda environment, database, reference data, frontend.

    [:octicons-arrow-right-24: Set up a development machine](setup/index.md)

-   :material-server:{ .lg .middle } **Deployment**

    ---

    Install on a Linux server, release updates and operate the services.

    [:octicons-arrow-right-24: Deploy GEIDA](deploy/index.md)

-   :material-history:{ .lg .middle } **Changelog**

    ---

    Every change to the platform, by release date.

    [:octicons-arrow-right-24: View the changelog](changelog.md)

-   :material-bullhorn:{ .lg .middle } **Updates**

    ---

    Release notes: what changed for users, and what administrators must do.

    [:octicons-arrow-right-24: Read the updates](updates/index.md)

</div>

## At a glance

| | |
|---|---|
| **Owner** | Islamic Development Bank (IsDB) |
| **Developed by** | Terra, Expo City Dubai |
| **Live site** | [geida.terrawatch.net](https://geida.terrawatch.net) (staging) |
| **Backend** | Django 6 + GeoDjango JSON API, Celery + Redis worker, PostgreSQL + PostGIS (development and production) |
| **Frontend** | React 19, TypeScript, Vite 8, MapLibre GL, GeoLibre GIS workspace |
| **Raster data** | Cloud-optimised GeoTIFFs, drawn and cut by TiTiler |
| **Vector data** | OpenStreetMap (Geofabrik extracts), GADM administrative boundaries |
| **Source code** | `isdb_geida` repository: `backend/`, `frontend/`, `docs/`, `deploy/` |

!!! tip "New to the project?"
    Read [Introduction](introduction/index.md) and [Architecture](architecture/index.md) first,
    then follow [Local development](setup/local-development.md). A first setup takes about
    30 minutes, most of it downloading packages.

