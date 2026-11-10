"""
Send analysis runs stuck in 'queued' back to Celery (e.g. after Redis was restarted
and lost its queue). With --stale N, runs left 'running' for more than N minutes are
re-queued too.

    python manage.py requeue_runs [--stale 90]
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.analysis.models import ModuleRun
from apps.analysis.tasks import run_module


class Command(BaseCommand):
    help = "Re-send queued (and optionally stale running) analysis runs to the Celery queue."

    def add_arguments(self, parser):
        parser.add_argument("--stale", type=int, default=0, help="Also re-queue runs running longer than N minutes")

    def handle(self, *args, stale=0, **opts):
        if stale:
            cutoff = timezone.now() - timedelta(minutes=stale)
            n = ModuleRun.objects.filter(status="running", started__lt=cutoff).update(status="queued")
            self.stdout.write(f"{n} stale running run(s) reset to queued.")
        ids = list(ModuleRun.objects.filter(status="queued").order_by("created").values_list("id", flat=True))
        for run_id in ids:
            run_module.delay(run_id)
        self.stdout.write(f"Sent {len(ids)} queued run(s) to Celery.")
