# Seeds

Reference data a fresh GEIDA database needs before anyone can use it. The
schema comes from migrations; the content comes from here.

```bash
python manage.py migrate
python manage.py seed                 # CRI library + analysis modules
python manage.py seed --boundaries    # also GADM admin units (needs backend/data/boundaries/)
```

Every step is idempotent: records are matched on a natural key (CRI code,
module id, GADM gid) and updated in place, so `seed` is safe to run on every
deploy.

## What gets loaded

| Step | Source | Target | Command on its own |
|---|---|---|---|
| CRI library | `seeds/data/isdb_cri_2025_seed.csv` (77 IsDB Core Result Indicators, 2025 poster) | `projects.CRI` | `load_cri [path]` |
| Analysis modules | `backend/modules/<id>/manifest.yaml` | `analysis.Module` | `sync_modules` |
| Admin boundaries (`--boundaries`) | `backend/data/boundaries/gadm41_adm0-3*.gpkg` (not in git, ~4.5 GB) | `boundaries.AdminUnit` | `load_admin_units` |
| Role groups | data migration `projects/0002_user_groups` | `auth.Group` | runs with `migrate` |

`seeds/data/isdb_member_countries.geojson` is read directly at runtime (country
pickers, Geo-Portal outlines) rather than loaded into a table.

## Rules

- **Codes are data.** CRI codes, module ids and country lists live in these files,
  never in Python. When IsDB revises the CRI list, replace the CSV and re-run
  `seed`.
- **Small files only.** Anything over a few MB (rasters, GADM) belongs in
  `backend/data/`, which is git-ignored and copied onto each server.
- **New reference table?** Add its file under `seeds/data/`, a loader command in
  the owning app, and a step in `apps/core/management/commands/seed.py`.
