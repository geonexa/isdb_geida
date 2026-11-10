# Troubleshooting

## Backend

??? failure "`Symbol not found: _GEOS…` or `proj.db contains DATABASE.LAYOUT.VERSION…`"
    A geospatial library from outside the `geida` environment was loaded (Homebrew, pip
    wheels or the `defaults` channel).

    1. Open a **new terminal** (old `DYLD_*` variables are a common cause), or run
       `unset DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH`.
    2. `conda activate geida` and run `python manage.py check`. The start-up check
       `geida.E001` names the conflicting PROJ installation.
    3. If it persists, rebuild the environment:
       `conda env remove -n geida && conda env create -f environment.yml`.

    Never `pip install` GDAL, rasterio, pyproj, fiona or shapely into `geida`.

??? failure "`CondaHTTPError: HTTP 000 CONNECTION FAILED`"
    A network interruption while conda downloaded packages. Run the same command again;
    conda resumes. Behind a proxy, configure `proxy_servers` in `~/.condarc`.

??? failure "`Error: That port is already in use` on `runserver`"
    Another `runserver` is still running. Find it with `lsof -i :8000` and stop it, or run
    on another port (`python manage.py runserver 8001`, then
    `GEIDA_BACKEND=http://127.0.0.1:8001 npm run dev`).

??? failure "`manage.py: No such file or directory`"
    Django commands run from `backend/`: `cd backend` first.

??? failure "An analysis stays *queued*"
    The worker is not running or cannot reach Redis.

    - Start it: `python manage.py run_worker` (needs Redis: `redis-cli ping` → `PONG`).
    - Or set `CELERY_TASK_ALWAYS_EAGER=true` in `.env` for development.
    - After Redis restarted, re-queue: `python manage.py requeue_runs`.

??? failure "An analysis fails with `OSMUnavailable`"
    Neither the Geofabrik extract nor Overpass could be reached. Check internet access to
    `download.geofabrik.de`, or copy the country's `.osm.pbf` into `DATA_DIR/osm/`.

??? failure "Emails don't arrive"
    With `EMAIL_HOST_USER` empty, emails are printed in the `runserver` console by design.
    For real sending, set the `EMAIL_*` variables ([Configuration](configuration.md)); for
    Gmail use an app password.

## Frontend

??? failure "The page loads but every API call fails (404 or HTML instead of JSON)"
    The Django server isn't running on :8000, or the proxy points elsewhere. Start
    `runserver`, or set `GEIDA_BACKEND`. Always open the app on **:5173**, not :8000.

??? failure "`npm run build` is killed or runs out of memory"
    The full build (type-check plus GeoLibre bundles) needs about 6 GB of RAM. Close other
    applications, or build on a larger machine and copy `frontend/dist/` to the server.

??? failure "Raster layers don't appear on the map"
    Raster layers come from TiTiler (`TITILER_URL`). Check that it answers:
    `curl -sI https://titiler.waterinag.org/healthz`. Some layers only draw from a minimum
    zoom level (land cover from zoom 7, terrain from zoom 8); zoom in.

??? failure "Vite reloads the page the first time a feature opens"
    In development, Vite optimises new dependencies the first time they are imported and
    then reloads once. It does not happen in a production build.

## Getting help

1. Search this documentation (top bar).
2. Check the component READMEs
   (`backend/README.md`, `frontend/README.md`, `deploy/README.md`).
3. Contact the GEIDA development team at Terra, Expo City Dubai.
