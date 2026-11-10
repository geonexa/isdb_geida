# GEIDA Frontend

The GEIDA single-page app: public site, accounts, project onboarding and project
workspace, the Geo-Portal, and the Analytics GIS workspace (GeoLibre). React 19,
TypeScript and Vite 8, with MapLibre GL for project maps and OpenLayers for the
classic Geo-Portal.

It talks only to the Django API under `/api/`. In development Vite proxies `/api`
and `/admin` to Django on :8000; in production Apache serves `dist/` and proxies
the same paths, so the browser always sees one origin.

## Contents

- [Architecture](#architecture)
- [Project layout](#project-layout)
- [Routes](#routes)
- [Data flow](#data-flow)
- [GIS workspace (GeoLibre)](#gis-workspace-geolibre)
- [Setup](#setup)
- [Scripts](#scripts)
- [Conventions](#conventions)

## Architecture

```
index.html ─► src/app/main.tsx
               ├─ QueryClientProvider (React Query)┐
               ├─ AuthProvider (session user)      │
               ├─ ToastProvider                    │ shared state
               └─ RouterProvider (src/app/router)  ┘
                    ├─ Layout (Navbar, Footer) ─► site, projects, geoportal pages
                    ├─ AuthLayout              ─► sign-in, register, verify, reset
                    └─ lazy chunks: Analytics (GisApp), Geo-Portal, Projects
                              │
                              └─ shared/api/client.ts ──► /api/* (Django)
```

- **Feature folders.** Each product area owns its pages, components, types and
  styles under `src/features/<name>/`; cross-cutting code sits in `src/shared/`.
- **Lazy by default.** Heavy areas (GIS workspace, Geo-Portal, project pages) are
  split into their own chunks and loaded on first visit.
- **One API client.** `shared/api/client.ts` adds the session cookie and the
  `X-CSRFToken` header, and turns Django error JSON into `ApiError` (with field errors).

## Project layout

```
frontend/
├── src/
│   ├── app/                      application shell
│   │   ├── main.tsx              entry: providers + router
│   │   ├── router.tsx            all routes, lazy imports
│   │   └── layout/               Layout, AuthLayout, Navbar, Footer
│   ├── features/
│   │   ├── auth/                 AuthContext, pages/ (SignIn, Register, Verify, PasswordReset)
│   │   ├── site/                 Home, ModulePage (content sections), NotFound
│   │   ├── projects/             list, wizard (steps/), detail workspace (workspace/),
│   │   │                         import, analyses panel, ProjectMap (MapLibre), projects.css
│   │   ├── geoportal/            GeoPortalPage, OpenLayers engine/, geoportal.css
│   │   ├── gis/                  GisWorkspacePage: mounts the GeoLibre workspace
│   │   └── print/                map export composer (PrintDialog), off-screen capture, PNG/PDF/SVG/print
│   ├── shared/
│   │   ├── api/                  client.ts (fetch wrapper), types.ts (API types)
│   │   ├── components/           Field, Toasts, icons, BasemapPicker
│   │   ├── lib/                  dom and site helpers
│   │   ├── map/                  basemaps.ts: shared basemap list (API), remembered choice
│   │   └── styles/               geida.css (design system), basemap.css (picker, also used by the Geo-Portal)
│   └── vite-env.d.ts
├── gis/                          GeoLibre workspace source (MIT, vendored): apps/web, packages/*
├── public/                       images, member-country GeoJSON, processing worker
├── scripts/                      build helpers (engine copy, GIS env, CSS scoping)
├── patches/                      patch-package fixes for dependencies
├── vite.config.ts                one Vite app for GEIDA + GeoLibre, dev proxy
└── tsconfig*.json                `@/` → `src/`
```

## Routes

| Path | Page | Access |
|---|---|---|
| `/` | Home | public |
| `/:slug` | content section (eToolkit, Knowledge Hub, …) | public |
| `/projects` | project list | public (published), own drafts when signed in |
| `/projects/new`, `/projects/:code/edit` | onboarding wizard | signed in |
| `/projects/:code` | project workspace (overview, map, indicators, analyses) | by project status |
| `/projects/import` | bulk import | signed in |
| `/projects/review` | review queue | reviewers |
| `/geoportal` | Geo-Portal (Earth Engine layers, area tools) | public |
| `/analytics` | GIS workspace (GeoLibre) | analysts |
| `/accounts/sign-in`, `register`, `verify`, `password-reset/...` | accounts | public |

`/geo-portal` and `/geo-portal/classic` redirect to `/geoportal`.

## Data flow

1. `AuthProvider` loads `GET /api/auth/me/` once and exposes the user and their
   roles (`is_reviewer`, `is_analyst`) to every page.
2. Pages fetch with `api()` from `@/shared/api/client`, wrapped in React Query
   hooks (`features/*/data.ts(x)`) that cache server state.
3. Writes go through the same client, which fetches a CSRF cookie first if missing.
4. Active analysis runs are re-fetched every 2.5 s (React Query `refetchInterval`) until they finish;
   results (layers, tables, previews) are served from `runs/<id>/files/<name>`.

## GIS workspace (GeoLibre)

`/analytics` renders the full GeoLibre workspace (Project, Edit, View, Add Data,
Processing, Plugins, Settings) below the GEIDA navbar. Its source lives in
`gis/` and is ours to change (MIT, see `gis/LICENSE`); keep edits small so
upstream fixes can still be merged.

- **One build.** npm workspaces link `gis/packages/*`; `vite.config.ts` reuses
  GeoLibre's plugins from `gis/apps/web/vite.config.ts`. `features/gis` mounts
  `GisApp` through the `virtual:gis-mount` module, loaded on first visit.
- **Print engine.** `features/print` draws pages with GeoLibre's print-layout
  engine (`gis/apps/web/src/lib/print-layout.ts`) through `virtual:gis-print`
  and `virtual:gis-print-svg`, typed in `features/print/gis-print.d.ts`. Update
  that declaration if GeoLibre's `LayoutOptions` changes.
- **Isolated styles.** `scripts/postcss-scope-gis.mjs` scopes GeoLibre's Tailwind
  to `<html class="gis-active">` and GEIDA's CSS to everything else at build time.
- **Static files.** `gis/apps/web/public` is served at `/gis-assets/` and copied
  to `dist/gis-assets/`.
- **Deep links:** `/analytics?data=https://example.org/layer.geojson`, `/analytics?tool=slope`.
- **Notebook panel** needs JupyterLite:
  `pip install -r gis/apps/web/jupyterlite/requirements.txt && node gis/scripts/build-jupyterlite.mjs`.
- **Processing engine.** `geolibre-wasm` is copied into `public/vendor/` by
  `npm run dev` / `build` (or `npm run engine`), so no code loads from a CDN.

## Setup

Requires Node 22+ and the backend running on :8000.

```bash
cd frontend
npm install          # first time: ~2 GB, 1–3 minutes (also applies patches)
npm run dev          # http://localhost:5173
```

Point the dev proxy at another backend with `GEIDA_BACKEND=http://host:port npm run dev`.

Production build: `npm ci && npm run build` → `dist/` (needs ~6 GB RAM for the
type-check and GeoLibre bundles). Apache serves it; see `../deploy/README.md`.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | dev server on :5173 with API proxy |
| `npm run build` | copy engine, type-check everything, build → `dist/` |
| `npm run typecheck` | type-check GEIDA and GeoLibre (`tsc -b`) |
| `npx tsc -p tsconfig.app.json --noEmit` | type-check GEIDA sources only (seconds) |
| `npm run test:gis` | GeoLibre unit tests |
| `npm run preview` | serve the built `dist/` locally |

## Conventions

- **Where code goes:** a new product area → `src/features/<name>/`; anything used
  by two or more features → `src/shared/`; routes and shell → `src/app/`.
- **Imports:** `@/…` across features (`@/shared/api/client`), relative paths
  only inside one feature.
- **Styles:** design tokens and base components in `shared/styles/geida.css`;
  feature styles next to the feature, imported by its entry component.
- **Types:** API shapes in `shared/api/types.ts` or the feature's `types.ts`;
  `strict` TypeScript, no unused locals.
- **Maps:** MapLibre for new map views; the OpenLayers Geo-Portal is legacy and
  will be folded into MapLibre. Every map uses the same basemaps (`useBasemaps()`,
  from the backend catalogue) and `<BasemapPicker>`; the choice is remembered in
  `localStorage["geida.basemap"]`, shared with the Geo-Portal. Add a basemap in
  `backend/apps/geoportal/catalog.py` (`BASEMAPS`) and every map gets it.
