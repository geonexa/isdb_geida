# Reference data

A fresh database gets its **schema** from migrations and its **content** from the `seed`
command, which reads one catalogue: `REFERENCE_DATA_DIR/catalog.json`. It lists every dataset
GEIDA stores itself, small (CRI library, IsDB member countries, OSM taxonomy) and large (GADM
boundaries, HydroATLAS basins / rivers / lakes), with its files, table, loader, source and
licence. Registering the analyses in `backend/analyses/` (`sync_modules`) is a built-in step of
the same command.

Data that can be read where it is published (OpenStreetMap, Copernicus DEM, WaPOR, WorldCover,
JRC surface water, Overture, …) is never seeded: analyses read it by area and cache it in
`DATA_DIR`.

## Folders

| Setting | Default | Holds |
|---|---|---|
| `REFERENCE_DATA_DIR` | `geida_static_data/` next to the repository folder | One folder per dataset, `catalog.json`, `README.md`, `catalog.html` (viewer). Not in git |
| `DATA_DIR` | `.cache/` in the repository (git-ignored) | Runtime cache: dataset clips per area, OSM extracts, derived products. Safe to delete |

```
GEIDA_Platform/
├── isdb_geida/                 the repository
│   └── .cache/                 DATA_DIR (runtime cache, git-ignored)
└── geida_static_data/          REFERENCE_DATA_DIR
    ├── catalog.json            every dataset: files, table, load, source, licence
    ├── catalog.html            the catalogue as a web page
    ├── IsDB_CRI_Library/       isdb_cri_2025_seed.csv
    ├── IsDB_Member_Countries/  isdb_member_countries.geojson
    ├── OSM_Taxonomy/           osm_taxonomy.yaml
    ├── Admin_Boundaries/       GADM 4.1 (prepared GeoPackages)
    ├── BasinATLAS_Data_v10_shp/, RiverATLAS_Data_v10_shp/, LakeATLAS_Data_v10_shp/
    └── _prepared/              written by loaders (GeoParquet, load files)
```

The app finds files it reads at run time through the catalogue
(`apps.reference.catalog.dataset_file("member_countries")`), never a hard-coded path.

## The seed command

```bash
cd backend
python manage.py seed list                     # every dataset: files, rows, last load
python manage.py seed                          # everything marked required (new installation)
python manage.py seed --only gadm --countries UGA,AZE   # one dataset, some countries
python manage.py seed --only gadm --path /other/disk/Admin_Boundaries
python manage.py seed --dry-run                # what would be done
```

- The analysis registry and small datasets are re-applied on every run (idempotent loaders); the release script runs `seed`
  on every deploy.
- Large datasets are loaded once and skipped while their files are unchanged; `--force`
  reloads. One already in the database with no load recorded is recorded, not reloaded.
- Every step is recorded in `reference.ReferenceDataset` (dataset, version, folder, files,
  fingerprint, rows, source, licence, date), visible in the admin.

| Dataset | Loaded into | Loader (`load.kind`) |
|---|---|---|
| `analysis_modules` (built-in step) | `analysis.Module` | `sync_modules` |
| `cri` (77 indicators) | `projects.CRI` | `load_cri` (command) |
| `member_countries` | read at run time; copied to `frontend/public/data/` | publish |
| `osm_taxonomy` | read at run time | runtime |
| `gadm` (GADM 4.1, levels 0–3) | `boundaries.AdminUnit` | `load_admin_units` (command) |
| `hydrobasins`, `hydrorivers`, `hydrolakes` | `reference.Basin`, `River`, `Lake` | pending |
| User groups | `auth.Group` | migration `projects/0002_user_groups` |

## Getting the reference data folder

Copy `geida_static_data/` from the team's shared drive (about 33 GB; a new installation needs at least the small folders and `Admin_Boundaries/`) and set
`REFERENCE_DATA_DIR` in `backend/.env` if it isn't next to the repository. Its `README.md` and
`catalog.json` list every dataset with its download link, so the folder can also be rebuilt from
the publishers. GADM's GeoPackages are prepared from GADM's "levels" GeoPackage:

```bash
cd backend
python apps/reference/prepare/prepare_gadm.py gadm_410-levels.gpkg $REFERENCE_DATA_DIR/Admin_Boundaries
```

## OpenStreetMap extracts

Downloaded automatically from Geofabrik the first time a country is analysed, into
`DATA_DIR/osm/` (up to 2 GB per country). On a server without internet access, copy the
`.osm.pbf` files there by hand. To refresh a country, delete its extract.

## Updating reference data

| Change | Do |
|---|---|
| IsDB revises the CRI list | Replace `IsDB_CRI_Library/isdb_cri_2025_seed.csv` (same columns), run `seed`, add a changelog entry |
| New or changed analysis | Edit `backend/analyses/<category>/<id>/`, run `seed` (or `sync_modules`) |
| New OSM theme | Add it to `OSM_Taxonomy/osm_taxonomy.yaml`; no code change |
| New version of a large dataset | Put it in its folder in `REFERENCE_DATA_DIR`, update its catalogue entry (version, files, counts), run `seed --only <id>` |
| New dataset | A folder plus a catalogue entry with its `load` block; see the folder's `README.md` |

!!! danger "Codes are data"
    Never hard-code CRI codes, module ids or country lists in Python or TypeScript. Change
    the data files and run `seed`.
