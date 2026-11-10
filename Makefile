# GEIDA developer shortcuts. Run `make help`.
# Backend targets expect the conda env to be active: `conda activate geida`.

SHELL := /bin/bash
PY    := python
BE    := cd backend &&
FE    := cd frontend &&

.DEFAULT_GOAL := help
.PHONY: help setup setup-backend setup-frontend migrate seed seed-all \
        backend worker frontend test test-backend test-frontend check build clean

help: ## List targets
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: setup-backend setup-frontend ## First-time setup (backend + frontend)

setup-backend: ## Create .env if missing, migrate, seed
	@test -f backend/.env || cp backend/.env.example backend/.env
	$(BE) $(PY) manage.py migrate && $(PY) manage.py seed

setup-frontend: ## Install frontend dependencies
	$(FE) npm install

migrate: ## Apply database migrations
	$(BE) $(PY) manage.py migrate

seed: ## Load reference data (CRI library, analysis modules)
	$(BE) $(PY) manage.py seed

seed-all: ## Reference data + GADM admin boundaries (slow)
	$(BE) $(PY) manage.py seed --boundaries

backend: ## Django dev server on :8000
	$(BE) $(PY) manage.py runserver

worker: ## Celery worker for analysis runs (needs Redis)
	$(BE) $(PY) manage.py run_worker

frontend: ## Vite dev server on :5173
	$(FE) npm run dev

test: test-backend test-frontend ## All tests

test-backend: ## Django tests
	$(BE) $(PY) manage.py test

test-frontend: ## GIS workspace unit tests
	$(FE) npm run test:gis

check: ## Django system checks, missing migrations, frontend type-check
	$(BE) $(PY) manage.py check && $(PY) manage.py makemigrations --check --dry-run
	$(FE) npm run typecheck

build: ## Production frontend build -> frontend/dist
	$(FE) npm run build

clean: ## Remove build output and caches (keeps data and database)
	rm -rf frontend/dist backend/staticfiles
	find backend -name __pycache__ -type d -prune -exec rm -rf {} +
