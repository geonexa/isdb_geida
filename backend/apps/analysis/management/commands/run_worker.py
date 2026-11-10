"""
Start the Celery worker for analysis runs (shortcut for `celery -A config worker`).

    python manage.py run_worker            # macOS: --pool solo (one run at a time)
    python manage.py run_worker -c 2       # Linux: 2 runs in parallel (prefork)

In DEBUG the worker restarts itself when Python code changes (like runserver);
pass --noreload to turn that off.

Needs Redis running (REDIS_URL, default redis://localhost:6379/0). On a server, run
`celery -A config worker -l info -c 2` as a systemd service instead.
"""
import platform

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import autoreload

from apps.analysis.envcheck import raster_env_problem
from config.celery import app


class Command(BaseCommand):
    help = "Start the Celery worker that runs analysis modules."

    def add_arguments(self, parser):
        parser.add_argument("-c", "--concurrency", type=int, default=0)
        parser.add_argument("-l", "--loglevel", default="info")
        parser.add_argument("--noreload", action="store_true", help="Don't restart the worker when code changes.")

    def handle(self, *args, concurrency=0, loglevel="info", noreload=False, **opts):
        if settings.DEBUG and not noreload:
            autoreload.run_with_reloader(self.start, concurrency, loglevel)
        else:
            self.start(concurrency, loglevel)

    def start(self, concurrency, loglevel):
        if problem := raster_env_problem():
            self.stderr.write(self.style.WARNING(f"Warning: analyses will fail. {problem}"))
        argv = ["worker", f"--loglevel={loglevel}"]
        if platform.system() == "Darwin" and not concurrency:
            # GDAL/rasterio and forked processes don't mix well on macOS.
            argv.append("--pool=solo")
        else:
            argv.append(f"--concurrency={concurrency or 2}")
        app.worker_main(argv)
