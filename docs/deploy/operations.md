# Operations

## Services

| Service | Unit | What it runs |
|---|---|---|
| API | `geida-api` | Gunicorn, 3 workers, `127.0.0.1:8012`, 180 s timeout |
| Worker | `geida-worker` | Celery, 2 concurrent analyses |
| Web server | `apache2` | HTTPS, static files, proxy |
| Database | `postgresql` | PostgreSQL + PostGIS |
| Queue | `redis-server` | Celery broker |

```bash
sudo systemctl status  geida-api geida-worker
sudo systemctl restart geida-api geida-worker      # after changing backend/.env
sudo systemctl reload  geida-api                   # graceful Gunicorn reload
sudo systemctl reload  apache2                     # after changing the virtual host
```

## Logs

| Log | Command |
|---|---|
| API (requests, errors) | `journalctl -u geida-api -f` |
| Analysis runs | `journalctl -u geida-worker -f` |
| Apache access | `sudo tail -f /var/log/apache2/geida_access.log` |
| Apache errors | `sudo tail -f /var/log/apache2/geida_error.log` |

A failed run also keeps its own log, visible on the run in the project's Analyses tab and
in `/admin` → *Module runs*.

## Backups

| What | Where | How often |
|---|---|---|
| Database | PostgreSQL `geida` | Daily, and before every release with migrations |
| Run outputs and uploads | `backend/media/` | Daily |
| Configuration | `backend/.env` | After every change, to a secure location |
| Large datasets | `DATA_DIR` | Not needed: boundaries can be copied again, OSM and cache re-download |

```bash
# Database
pg_dump -Fc -U geida -h localhost geida > geida-$(date +%F).dump
# Restore into an empty database
pg_restore -U geida -h localhost -d geida --clean geida-2026-11-09.dump

# Media
tar czf geida-media-$(date +%F).tar.gz -C ~/geida_platform_react/backend media
```

## Routine tasks

| Task | How |
|---|---|
| Re-queue runs stuck after a Redis restart | `python manage.py requeue_runs` (add `--stale 90` for runs *running* over 90 minutes) |
| Refresh a country's OSM data | Delete `DATA_DIR/osm/<region>.osm.pbf`; the next run downloads the current extract |
| Free disk space | Delete `DATA_DIR/cache/` (rebuilt on demand) |
| Renew the certificate | Automatic with certbot's timer; check with `sudo certbot renew --dry-run` |
| Add a reviewer or analyst | `/admin` → *Users* → groups `GEIDA reviewers` / `GEIDA analysts` |

## Monitoring

At minimum, check every day that:

- `curl -sI https://<site>/api/site/` returns `200`;
- `systemctl is-active geida-api geida-worker` prints `active` twice;
- the disk holding `DATA_DIR` and `media/` has more than 10 GB free (`df -h`).
