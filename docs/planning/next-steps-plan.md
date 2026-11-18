# GEIDA: next steps (18 Nov 2026 → hand-over)

Status: plan for discussion, 18 Nov 2026. Replaces the open parts of `docs/plan.md` (last updated 4 Nov),
which no longer reflects what is built. Not on the docs site (`docs/planning/` is excluded).

Time left: about six working weeks to the end of Cycle 2 (31 Dec 2026), then January for hand-over
(workplan M7–8).

## 1. Where GEIDA stands

**Built and working locally** (183 backend tests pass; the last commit is from 12 Nov, so everything since,
including the 16 Nov release, is not on the server):

| Area | What exists |
|---|---|
| Projects | Onboarding (wizard, bulk and submission-form import), CRI library, review workflow, area of influence, Results Framework (baseline and target) |
| Analyses | 26 analyses in 6 categories: Terrain (5), Water (3 hydrology), Land (6), People (5), Infrastructure (5), Planning (suitability). 70+ planned analyses listed, 9 of them already showing their data ("Data only") |
| Toolbox | 186 server-side tools (GeoLibre engine on the Celery worker), results saved with the project |
| Reports | Reports tab: frozen versions as PDF and web report, interactive maps, globe cover, share links |
| Map | Project map with time series player (Wayback, monthly NDVI, yearly WaPOR), layout editor (PDF to 600 dpi) |
| Analytics | GeoLibre workspace with the project's layers, trimmed of US-only, keyed and external items |
| Data | Data Catalog (COGs via TiTiler: WaPOR L1, WorldCover, Copernicus DEM, JRC water, WorldCereal, MODIS, Wayback), GADM boundaries, OSM extracts |

**Gaps that matter for IsDB's project cycle:**

- **Implementation and completion phases are thin.** Most analyses serve preparation (PPRR); supervision
  (PIASR) and completion (PCR) need change-over-time analyses: monitoring, hazards, water trends.
- **No progress tracking on indicators.** The Results tab shows baseline and target but not progress over
  time, and nothing exports the logframe layout IsDB documents use.
- **Water resources is mostly planned.** WaPOR L1 data is already readable; the analyses are not built.
- **Not deployed, not tested end to end.** Two weeks of work (reports, server Toolbox, Analytics changes,
  time series) exist only on this machine; there is no browser smoke test and no CI.
- **Hazards and Monitoring categories have no analyses at all.**

## 2. The plan

### Step 1: Consolidate and ship (this week, 18–22 Nov)

| # | Task | Done when |
|---|---|---|
| 1.1 | Commit the current work (you commit in one batch) | Clean `git status` |
| 1.2 | Deploy to the server, following the 16 Nov update note plus the Analytics `deployment.json` and the Vite base-URL fix | geida.terrawatch.net shows reports, Toolbox and the trimmed Analytics; a run and a report version complete there. **Only when you say: nothing on the server until you ask** |
| 1.3 | Browser smoke test (Playwright): home, projects, workspace tabs, a run, a report, Analytics | Script passes locally and against the server |
| 1.4 | CI: backend tests and the smoke test on every push | Green on the repository |
| 1.5 | Rewrite `docs/plan.md` from this document | `plan.md` matches what is built |
| 1.6 | Feedback from the IsDB update meeting folded into this plan | Priorities below confirmed or reordered |

### Step 2: Water resources wave 1 on WaPOR L1 (23 Nov – 6 Dec)

**Started 18 Nov:** the WaPOR time series analysis is built (any L1 layer, dekadal / monthly / annual, at a point
or per polygon, with chart and trend), with the shared WaPOR reader (`apps/analysis/data/wapor.py`), the trend
test (`apps/analysis/ops/timeseries.py`) and chart outputs. That covers task 2.0; the analyses below can now
build on it.

All on WaPOR v3 **L1** (300 m, global), data GEIDA already reads. Each replaces a "Data only" row in the
Analyses tab with a runnable analysis.

| # | Analysis | Output |
|---|---|---|
| 2.0 | **Time series helper and chart output** (shared): yearly or monthly values over the area, anomaly against a baseline, Mann-Kendall / Sen's slope trend | Line and bar charts in run results and reports |
| 2.1 | Precipitation | Yearly total map, series 2018 onwards, anomaly of the chosen year |
| 2.2 | Evapotranspiration (ETa, T, E, I) | Maps and shares of each component |
| 2.3 | Water balance (P − ETa) | Surplus / deficit map and series |
| 2.4 | ET deficit and water stress (ETa vs RET) | Stress map, share of cropland under stress |
| 2.5 | Water productivity and gap (GBWP / NBWP) | Productivity map, gap to the 95th percentile |
| 2.6 | Surface water occurrence and change (JRC) | Permanent / seasonal / lost / new water, areas |

The time series helper also unlocks Seasonal profile and anomaly (MODIS NDVI) and the monitoring analyses in
step 4, so it comes first.

### Step 3: Results tracking and IsDB reporting (7–13 Dec)

| # | Task | Why |
|---|---|---|
| 3.1 | **Indicator tracker** in the Results tab: progress points per indicator (from accepted evidence or entered by hand), chart of baseline → progress → target | Supervision needs "is it on track?" per CRI |
| 3.2 | Logframe export in the PPRR / PIASR / PCR layout (Excel and PDF) | Matches the documents task managers already submit |
| 3.3 | Report presets per phase (PPRR annex, PIASR, PCR) with an evidence section and Toolbox results | One click to the document a phase needs |
| 3.4 | Email notifications in the review workflow (submitted, returned, published) | Reviewers don't have to poll the queue |

### Step 4: Monitoring and hazards, wave 1 (14–20 Dec)

| # | Analysis | Phase |
|---|---|---|
| 4.1 | Baseline snapshot: key figures recorded at appraisal | PPRR |
| 4.2 | Change since baseline: land cover, vegetation, water, buildings, roads | PIASR, PCR |
| 4.3 | Before and after imagery (Wayback and Sentinel-2 at two dates, side by side, for reports) | PIASR, PCR |
| 4.4 | Climate profile (ERA5 normals and trends via Open-Meteo, keyless) | PPRR |
| 4.5 | Flood-prone land (height above nearest drainage, from the hydrology work) | PPRR, PIASR |
| 4.6 | Heat (MODIS land surface temperature) | PPRR |

### Step 5: Platform for hand-over (21 Dec – 31 Dec, then January)

| # | Task | Notes |
|---|---|---|
| 5.1 | Roles: curated vs advanced users | Analytics and the Toolbox for analysts; a simpler set for task managers |
| 5.2 | Arabic and French in the GEIDA interface | IsDB's working languages; GeoLibre already has both |
| 5.3 | Country data upload (census tables, facility lists) joined to GADM units | Uganda NPHC 2024 first |
| 5.4 | Load the 10–15 anchor projects (Uganda, Azerbaijan, Mali first) with runs and a report each | Component B needs them |
| 5.5 | Acceptance against the Moroto case study | Results within tolerance |
| 5.6 | Admin and user guides, case studies | Docs site sections |
| 5.7 | IsDB single sign-on and ePIASR link | Only once IMDT confirms; prepare the hooks |

## 3. Later (after hand-over or if time allows)

- Network distance (OSRM or pgRouting) for access analyses; travel time to schools, clinics and markets.
- Electrification from night lights (NASA Black Marble needs a free Earthdata account on the server).
- Cropland and irrigated area with a readable WorldCereal copy; per-field statistics.
- Runoff estimate and water accounting summary (water wave 3).
- Sortable tables and public reports on published projects.
- The remaining "your call" items in `analytics-toolbar-review.md`.

## 4. Decisions needed

| # | Question | Recommendation | Who |
|---|---|---|---|
| 1 | Order of steps 2–4 after the IsDB meeting | Water first (data ready, many IsDB agriculture and water projects), then results tracking | IsDB / Sajid |
| 2 | When to deploy the current work | This week, so IsDB staff can try it | You |
| 3 | Logframe export layout | Get one real PPRR, PIASR and PCR template from IsDB | IsDB |
| 4 | Which 10–15 anchor projects to load | Uganda, Azerbaijan, Mali first | Sajid / IsDB |
| 5 | AI assistant (needs a provider and an IsDB policy) | Leave off until IsDB decides | IsDB |
| 6 | Licences: GADM at IsDB, Meta RWI (non-commercial) | Clear before relying on them | Sajid |
| 7 | Single sign-on | Ask IMDT for the identity provider and a test tenant | IMDT |

## 5. Risks

- **One developer, six weeks.** Keep one category per step; anything new goes to section 3.
- **Holiday period** (late December): step 5 may slip into January; steps 1–3 are the ones to protect.
- **Server capacity**: raster analyses and the Toolbox run on the Celery worker; check memory and disk
  before loading 15 projects.
- **Undeployed work grows**: deploying in step 1 keeps the gap between this machine and the server small.
