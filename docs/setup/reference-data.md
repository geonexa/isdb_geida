# Reference data

A fresh database gets its **schema** from migrations and its **content** from the
`seed` command. Large datasets that are too big for git live in `DATA_DIR`
(`backend/data/` by default) and are copied onto each machine.

## The seed command

```bash
cd backend
python manage.py seed                              # CRI library + analysis modules
python manage.py seed --boundaries                 # + GADM administrative units
python manage.py seed --boundaries --countries UGA,AZE   # boundaries for some countries only
```

Every step is **idempotent**: records are matched on a natural key (CRI code, module id,
GADM id) and updated in place. The release script runs `seed` on every deploy.

| Step | Source | Loaded into | Run on its own |
|---|---|---|---|
| CRI library | `backend/seeds/data/isdb_cri_2025_seed.csv` (77 indicators) | `projects.CRI` | `load_cri [path]` |
| Analysis modules | `backend/modules/<id>/manifest.yaml` | `analysis.Module` | `sync_modules` |
| Administrative units (`--boundaries`) | `DATA_DIR/boundaries/gadm41_adm0-3*.gpkg` | `boundaries.AdminUnit` | `load_admin_units` |
| User groups | Migration `projects/0002_user_groups` | `auth.Group` | runs with `migrate` |

`backend/seeds/data/isdb_member_countries.geojson` and `osm_taxonomy.yaml` are read at run
time, not loaded into tables.

## Large datasets (`DATA_DIR`)

```
backend/data/                       git-ignored, except README.md
├── boundaries/                     GADM 4.1, copy in by hand
│   ├── gadm41_adm0-3.gpkg              full resolution (~4 GB)
│   ├── gadm41_adm0-3_simplified.gpkg   for map display (~0.5 GB)
│   └── gadm41_adm0-3_summary.csv
├── osm/                            downloaded on first use
│   ├── geofabrik-index.json            region outlines (refreshed monthly)
│   └── <region>.osm.pbf                e.g. uganda.osm.pbf
├── datasets/                       optional overrides: <dataset id>/<ISO3>.tif | .geojson
└── cache/                          per-area downloads; safe to delete
```

### GADM boundaries

Get the GADM files from the team's shared drive, or rebuild them from GADM's "levels"
GeoPackage (`gadm_410-levels.gpkg` from [gadm.org](https://gadm.org)):

```bash
cd backend
python scripts/prepare_gadm.py gadm_410-levels.gpkg data/boundaries
```

### OpenStreetMap extracts

Downloaded automatically from Geofabrik the first time a country is analysed (up to 2 GB
per country; larger extracts are refused). On a server without internet access, copy the
`.osm.pbf` files into `DATA_DIR/osm/` by hand. To refresh a country, delete its extract.

## Updating reference data

| Change | Do |
|---|---|
| IsDB revises the CRI list | Replace `isdb_cri_2025_seed.csv` (same columns), run `seed`, add a changelog entry |
| New or changed analysis module | Edit `backend/modules/<id>/`, run `seed` (or `sync_modules`) |
| New OSM theme | Add it to `osm_taxonomy.yaml`; no code change |
| New kind of reference table | Add the file under `seeds/data/`, a loader command in the owning app, and a step in `apps/core/management/commands/seed.py` |

!!! danger "Codes are data"
    Never hard-code CRI codes, module ids or country lists in Python or TypeScript. Change
    the data files and run `seed`.
