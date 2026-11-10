# First-time installation

These steps install GEIDA on a new Ubuntu server. Run them as the application user
(`ecduser` in the provided files) with `sudo` rights. Allow about two hours, most of it
spent loading boundaries and building the frontend.

## 1. System packages

```bash
sudo apt update
sudo apt install -y apache2 postgresql postgis redis-server git certbot python3-certbot-apache
sudo a2enmod ssl proxy proxy_http headers expires deflate rewrite
```

Install Miniconda (or Miniforge) for the application user:

```bash
curl -fsSLO https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
bash Miniconda3-latest-Linux-x86_64.sh -b -p ~/miniconda3
~/miniconda3/bin/conda init bash && exec bash
```

Install Node.js 22 (needed to build the frontend):

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
```

## 2. Database

```bash
sudo -u postgres createuser geida -P            # choose a strong password
sudo -u postgres createdb geida -O geida
sudo -u postgres psql -d geida -c "CREATE EXTENSION postgis;"
```

## 3. Code and Python environment

```bash
cd ~
git clone <repository-url> geida_platform_react
cd geida_platform_react
conda env create -f backend/environment.yml
conda activate geida
```

## 4. Configuration

```bash
cp backend/.env.example backend/.env
nano backend/.env
```

Set at least: `DJANGO_ENV=production`, `DJANGO_SECRET_KEY`, the `POSTGRES_*` values,
`DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `FRONTEND_URL`, the `EMAIL_*`
values and, if data live on another disk, `DATA_DIR`. See the
[production example](../setup/configuration.md#example-production-env).

```bash
chmod 600 backend/.env
```

## 5. Large datasets

Copy the GADM files into `DATA_DIR/boundaries/` (default
`backend/data/boundaries/`); see [Reference data](../setup/reference-data.md). OSM
extracts download on first use; on a server without internet, copy them into
`DATA_DIR/osm/`.

## 6. Schema, reference data, static files

```bash
cd ~/geida_platform_react/backend
python manage.py check --deploy
python manage.py migrate
python manage.py seed --boundaries         # CRI library, modules, administrative units (slow)
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

## 7. Frontend build

```bash
cd ~/geida_platform_react/frontend
npm ci
npm run build                               # -> frontend/dist (needs ~6 GB RAM)
```

## 8. Services

```bash
cd ~/geida_platform_react
# Review User=, WorkingDirectory= and the conda path in both files first.
sudo cp deploy/systemd/geida-api.service deploy/systemd/geida-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now redis-server geida-api geida-worker
systemctl status geida-api geida-worker --no-pager
```

## 9. Apache and HTTPS

```bash
# Review ServerName and the /home/ecduser/... paths first.
sudo cp deploy/apache/geida.conf /etc/apache2/sites-available/geida.conf
sudo certbot certonly --apache -d geida.terrawatch.net
sudo a2ensite geida
sudo apache2ctl configtest && sudo systemctl reload apache2
```

Apache must be able to read `frontend/dist` and `backend/staticfiles`. If the home
directory is private: `chmod o+x /home/ecduser`.

## 10. Verify

| Check | Command or action | Expected |
|---|---|---|
| API | `curl -sI https://geida.terrawatch.net/api/site/` | First line `HTTP/2 200` |
| Web app | Open the site | Home page loads over HTTPS |
| Admin | `/admin`, sign in as the superuser | Admin dashboard |
| Worker | Run *Area profile* on a test project | Run finishes; `journalctl -u geida-worker` shows it |
| Email | Register a test account | Verification code arrives |

Then create the reviewer and analyst accounts ([Users and roles](../introduction/roles.md))
and record the installation in the [Changelog](../changelog.md).
