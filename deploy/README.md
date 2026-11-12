# Deployment

GEIDA runs on one Linux server: Apache serves the React build and proxies the
API to Gunicorn; a Celery worker runs analyses; PostgreSQL + PostGIS stores the
data; Redis queues the runs.

```
            HTTPS                                   ┌──────────────┐
 browser ──────────► Apache ── /api, /admin ──────► │ geida-api    │ Gunicorn :8012
                      │                             │ (Django)     │──┐
                      └── /, /assets ─► frontend/dist└──────────────┘  │  PostgreSQL
                                                    ┌──────────────┐  ├─ + PostGIS
                                    Redis ◄──────── │ geida-worker │──┘
                                                    │ (Celery)     │
                                                    └──────────────┘
```

| Path | What |
|---|---|
| `apache/geida.conf` | Virtual host: TLS, SPA fallback, cache headers, proxy to Gunicorn |
| `systemd/geida-api.service` | Gunicorn for the Django API |
| `systemd/geida-worker.service` | Celery worker for analysis runs |
| `scripts/deploy.sh` | Pull, migrate, seed, build, restart — run for every release |

The unit files assume user `ecduser`, the repo at
`/home/ecduser/isdb_geida` and conda at `/home/ecduser/miniconda3`
(the terrawatch server's layout). Adjust them to another server before copying.
On terrawatch the Apache site is `geida-platform.conf` (already enabled), so copy
`apache/geida.conf` over `/etc/apache2/sites-available/geida-platform.conf`.
The older template-based app in `/home/ecduser/isdb-geida` (runserver on :8011)
is retired by this setup.

## First-time setup (new server)

```bash
# 1. System packages (Ubuntu)
sudo apt install apache2 postgresql postgis redis-server git
sudo a2enmod ssl proxy proxy_http headers expires deflate rewrite

# 2. Database
sudo -u postgres createuser geida -P
sudo -u postgres createdb geida -O geida
sudo -u postgres psql -d geida -c "CREATE EXTENSION postgis;"

# 3. Code and environment
git clone <repo-url> ~/isdb_geida && cd ~/isdb_geida
conda env create -f backend/environment.yml && conda activate geida
cp backend/.env.example backend/.env       # DJANGO_ENV=production, secret key, POSTGRES_*
#   copy geida_static_data/ next to the repository (or set REFERENCE_DATA_DIR in .env); see docs/setup/reference-data.md

# 4. Database schema and reference data
cd backend
python manage.py migrate
python manage.py seed                     # required datasets: modules, CRI library, admin units (first run slow: ~4 GB)
python manage.py createsuperuser
python manage.py collectstatic --noinput

# 5. Frontend
cd ../frontend && npm ci && npm run build # -> frontend/dist

# 6. Services
sudo cp deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now geida-api geida-worker
sudo cp deploy/apache/geida.conf /etc/apache2/sites-available/
sudo a2ensite geida && sudo certbot certonly --apache -d geida.terrawatch.net
sudo systemctl reload apache2
```

## Every release

```bash
cd ~/isdb_geida
./deploy/scripts/deploy.sh             # or --backend to skip the frontend build
```

The script stops at the first failing step, so a broken migration never leaves
services restarted on half-updated code.

## Moving an existing server to the new layout (Nov 2026)

The restructure moved folders that the server's copy still has in the old place:

| Old | New | Action on the server |
|---|---|---|
| `static_data/`, `backend/data/` | `geida_static_data/` (reference data, `REFERENCE_DATA_DIR`) next to the repository, and `.cache/` (runtime cache, `DATA_DIR`) inside it | move GADM into `geida_static_data/Admin_Boundaries/`, copy `catalog.json`; delete the old cache |
| `analyses/` | `backend/analyses/` | none: comes with `git pull` |
| `backend/data/*.csv, *.geojson`, `osm_taxonomy.yaml` | `geida_static_data/` (`IsDB_CRI_Library/`, `IsDB_Member_Countries/`, `OSM_Taxonomy/`) | copy with the rest of `geida_static_data/` |
| `deploy/apache.conf` | `deploy/apache/geida.conf` | none unless the live config is a symlink |
| `config/settings.py` | `config/settings/` package | none: `DJANGO_SETTINGS_MODULE=config.settings` is unchanged |

## Checks after a deploy

```bash
systemctl status geida-api geida-worker
curl -sI https://geida.terrawatch.net/api/site/ | head -1      # HTTP/2 200
journalctl -u geida-worker -n 50                               # analysis runs
```
