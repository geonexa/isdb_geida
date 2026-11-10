# backend/data/

Large local datasets. **Git-ignored apart from this file**; copy onto each
machine (shared drive) or let the fetchers fill the cache. `DATA_DIR` in
`backend/.env` points elsewhere if the disk is elsewhere.

```
data/
├── boundaries/   GADM 4.1 levels 0–3 → `manage.py seed --boundaries`
│   ├── gadm41_adm0-3.gpkg              full resolution (~4 GB)
│   ├── gadm41_adm0-3_simplified.gpkg   for map display (~0.5 GB)
│   └── gadm41_adm0-3_summary.csv
├── osm/          Geofabrik country extracts, downloaded on first use
│   ├── geofabrik-index.json            region outlines (refreshed monthly)
│   └── <region>.osm.pbf                e.g. uganda.osm.pbf (~370 MB)
├── datasets/     manual overrides: <dataset id>/<ISO3>.tif | .geojson
└── cache/        open-data downloads clipped per project (safe to delete)
    └── osm/<region>/<snapshot>/        area GeoPackages + themed GeoJSON layers
```

To refresh a country's OSM data, delete its `osm/<region>.osm.pbf`; the next run
downloads the current extract (new snapshot date, new cache folder). On a server
without internet, copy the extracts in by hand.

Rebuild `boundaries/` from the GADM "levels" GeoPackage with
`python scripts/prepare_gadm.py gadm_410-levels.gpkg data/boundaries` (run in
`backend/`). GADM is free for non-commercial use; confirm the licence before
IsDB hosting.
