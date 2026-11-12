# Setup: prerequisites

This section takes a new developer from an empty machine to a running GEIDA. Follow the
pages in order:

1. **Prerequisites** (this page): the software to install first.
2. [Local development](local-development.md): get the code, create the environment, run
   the backend, worker and frontend.
3. [Configuration](configuration.md): every setting in `backend/.env`.
4. [Reference data](reference-data.md): what `seed` loads and the large datasets to copy.
5. [Troubleshooting](troubleshooting.md): known problems and their fixes.

To install GEIDA on a server, use [Deployment](../deploy/index.md) instead.

## Supported platforms

| Platform | Status |
|---|---|
| macOS 13+ (Apple silicon or Intel) | Used for development |
| Ubuntu 22.04 / 24.04 LTS | Used for servers; works for development |
| Windows | Use WSL 2 with Ubuntu |

## Required software

| Software | Version | Why | Install |
|---|---|---|---|
| **Git** | any recent | Get the code | macOS: `xcode-select --install`; Ubuntu: `sudo apt install git` |
| **Conda** (Miniconda, Miniforge or Anaconda) | 23+ | Python 3.12 and the geospatial libraries (GDAL, PROJ, GEOS, rasterio) from conda-forge | [Miniforge](https://github.com/conda-forge/miniforge) recommended |
| **Node.js** | 22 or newer | Frontend build | [nodejs.org](https://nodejs.org) or `nvm install 22` |
| **Redis** | 6+ | Queue for analysis runs | macOS: `brew install redis && brew services start redis`; Ubuntu: `sudo apt install redis-server` |

Redis is optional on a development machine if you run analyses inline
(`CELERY_TASK_ALWAYS_EAGER=true`, see [Configuration](configuration.md)).

## Hardware

| | Minimum | Recommended |
|---|---|---|
| RAM | 8 GB | 16 GB (the full frontend build needs about 6 GB) |
| Disk | 10 GB free | 20 GB+ (GADM boundaries 4.5 GB, OSM country extracts 0.1–2 GB each) |

## Network access

The platform downloads open data on demand. A development machine needs outbound HTTPS to:

| Host | For |
|---|---|
| `download.geofabrik.de` | OpenStreetMap country extracts |
| `titiler.waterinag.org` (or your `TITILER_URL`) | Raster tiles and clips |
| `earth-search.aws.element84.com` | Copernicus DEM tile search |
| `storage.googleapis.com` and AWS S3 (`*.s3.amazonaws.com`) | Raster files read by analyses: FAO WaPOR (Google Cloud Storage), ESA WorldCover and Copernicus DEM (AWS) |
| `server.arcgisonline.com`, `tiles.maps.eox.at`, `*.tile.opentopomap.org` | Basemaps |
| `conda.anaconda.org`, `registry.npmjs.org`, `pypi.org` | Package installation |

!!! warning "Use conda-forge only"
    GDAL, PROJ, GEOS and rasterio must all come from conda-forge, in one
    environment. Installing any of them with `pip` or Homebrew loads two versions of PROJ
    or GEOS and GeoDjango fails at start-up. See [Troubleshooting](troubleshooting.md).
