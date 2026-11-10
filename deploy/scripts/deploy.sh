#!/usr/bin/env bash
# Update a running GEIDA server to the latest code on its branch.
#
#   ./deploy/scripts/deploy.sh            # backend + frontend
#   ./deploy/scripts/deploy.sh --backend  # skip the frontend build
#
# Run on the server, from the repository root, as the app user. Assumes the
# first-time setup in deploy/README.md is done (conda env, .env, systemd units).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
CONDA_ENV="${CONDA_ENV:-geida}"
BACKEND_ONLY=false
[[ "${1:-}" == "--backend" ]] && BACKEND_ONLY=true

log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

cd "$REPO_DIR"
log "Pulling latest code"
git pull --ff-only

log "Backend: dependencies, migrations, reference data, static files"
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"
cd backend
conda env update -f environment.yml --prune --quiet
python manage.py check --deploy --fail-level ERROR
python manage.py migrate --noinput
python manage.py seed
python manage.py collectstatic --noinput

if ! $BACKEND_ONLY; then
  log "Frontend: install and build (needs ~6 GB RAM)"
  cd "$REPO_DIR/frontend"
  npm ci --no-audit --no-fund
  npm run build
fi

log "Restarting services"
sudo systemctl restart geida-api geida-worker
sudo systemctl reload apache2
systemctl --no-pager --lines=0 status geida-api geida-worker

log "Deployed $(git -C "$REPO_DIR" rev-parse --short HEAD)"
