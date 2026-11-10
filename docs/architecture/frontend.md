# Frontend

The frontend (`frontend/`) is one React single-page application that contains every GEIDA
screen, including the GeoLibre GIS workspace. It talks only to the Django API under
`/api/`.

## Stack

| Concern | Choice |
|---|---|
| Language | TypeScript (strict) |
| UI | React 19, React Router 7 |
| Build | Vite 8 (one build for GEIDA and GeoLibre) |
| Server state | TanStack React Query |
| Maps | MapLibre GL (project maps, map export), OpenLayers (Data Catalog), GeoLibre (Analytics) |
| Icons | lucide-react |
| Styles | Plain CSS with design tokens (`shared/styles/geida.css`); GeoLibre's Tailwind is scoped to the Analytics page |

## Application structure

```
frontend/src/
├── app/                   application shell
│   ├── main.tsx           entry point: providers and router
│   ├── router.tsx         every route, with lazy-loaded pages
│   └── layout/            Layout, AuthLayout, Navbar, Footer
├── features/              one folder per product area
│   ├── auth/              session user (AuthContext) and account pages
│   ├── site/              home page, content sections, 404
│   ├── projects/          list, wizard, import, workspace, ProjectMap
│   ├── geoportal/         Data Catalog (OpenLayers engine)
│   ├── gis/               mounts the GeoLibre workspace at /analytics
│   └── print/             map layout editor and export
└── shared/                code used by two or more features
    ├── api/               client.ts (fetch wrapper), API types
    ├── components/        Field, Toasts, Confirm, BasemapPicker, icons
    ├── lib/               DOM and site-content helpers
    ├── map/               shared basemap list and remembered choice
    └── styles/            design system, basemap picker, catalog window
```

Rules: a new product area goes in `features/<name>/`; anything used by two features moves
to `shared/`; imports across features use the `@/` alias (`@/shared/api/client`).

## Routes

| Path | Page | Access |
|---|---|---|
| `/` | Home | Public |
| `/:slug` | Content section (EO Toolkit, Knowledge Hub, …) | Public |
| `/projects` | Project list | Public (published); own drafts when signed in |
| `/projects/new`, `/projects/:code/edit` | Onboarding wizard | Signed in |
| `/projects/import` | Bulk import | Signed in |
| `/projects/review` | Review queue | Reviewers |
| `/projects/:code` | Project workspace | Depends on project status |
| `/geoportal` | Data Catalog | Public |
| `/analytics` | GIS workspace (GeoLibre) | Public today; can be limited to analysts |
| `/accounts/sign-in`, `/accounts/register`, `/accounts/verify`, `/accounts/password-reset/…` | Accounts | Public |

`/geo-portal` and `/geo-portal/classic` redirect to `/geoportal`.

## Data flow

1. `AuthProvider` loads `GET /api/auth/me/` once (which also sets the CSRF cookie) and
   exposes the user and roles to every page.
2. Pages read data with React Query hooks that call `api()` from
   `shared/api/client.ts`.
3. Writes use the same client. It sends `X-CSRFToken` and turns Django's error JSON
   into an `ApiError` with field errors.
4. Running analyses are re-fetched every 2.5 seconds until they finish.

## Maps

- **One basemap list.** Every map reads the basemaps from the backend catalogue
  (`GET /api/geoportal/basemaps/`) through `useBasemaps()` and shows the same
  `<BasemapPicker>`. The choice is remembered in the browser (`geida.basemap`). Add a
  basemap in `backend/apps/geoportal/catalog.py` and every map gets it.
- **Project map** (`features/projects/ProjectMap.tsx`): MapLibre map with the area of
  influence, run outputs (images and vectors), data-catalog tile layers and the map
  export button.
- **Map export** (`features/print/`): a layout editor that renders the page as SVG and
  exports SVG, PNG or PDF. The map items are captured from an off-screen MapLibre map at
  the page size and resolution, so prints are sharp at any paper size.

## GIS workspace (GeoLibre)

`/analytics` renders the GeoLibre workspace (MIT licence) below the GEIDA navbar. Its
source is vendored in `frontend/gis/` and built together with GEIDA:

- npm workspaces link `gis/packages/*`; `vite.config.ts` reuses GeoLibre's Vite plugins.
- `features/gis` mounts it through the `virtual:gis-mount` module, loaded on first visit.
- A PostCSS step scopes GeoLibre's styles to the Analytics page and GEIDA's styles to
  everything else.
- GeoLibre's static files are served at `/gis-assets/`.
- The processing engine (`geolibre-wasm`) is copied into `public/vendor/` at build time,
  so nothing loads from a CDN.

Keep changes inside `frontend/gis/` small and limited to what a GEIDA feature needs.

## Scripts

| Command | What it does |
|---|---|
| `npm run dev` | Development server on :5173 with the API proxy |
| `npm run build` | Copy the processing engine, type-check everything, build into `dist/` |
| `npm run typecheck` | Type-check GEIDA and GeoLibre |
| `npx tsc -p tsconfig.app.json --noEmit` | Type-check GEIDA sources only (seconds) |
| `npm run test:gis` | GeoLibre unit tests |
| `npm run preview` | Serve the built `dist/` locally |
