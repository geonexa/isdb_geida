"""Celery tasks for analysis runs. ModuleRun is the record of every run; the task only executes it."""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from .models import ModuleRun
from .core.runner import execute


def claim(run_id, redelivered=False):
    """Atomically take a run: queued -> running (or a run whose worker died, on redelivery)."""
    statuses = ["queued", "running"] if redelivered else ["queued"]
    if ModuleRun.objects.filter(pk=run_id, status__in=statuses).update(status="running"):
        return ModuleRun.objects.select_related("project", "module", "project__area").get(pk=run_id)
    return None


@shared_task(bind=True, name="analysis.run_module")
def run_module(self, run_id):
    redelivered = bool((self.request.delivery_info or {}).get("redelivered"))
    run = claim(run_id, redelivered)
    if run is None:  # cancelled, or already taken by another worker
        return
    try:
        execute(run)
    except SoftTimeLimitExceeded:
        ModuleRun.objects.filter(pk=run_id).update(
            status="failed", error="The analysis took too long and was stopped. Try a smaller area.",
            finished=timezone.now())


def enqueue(run):
    """Send a run to the queue. Returns an error message if Redis can't be reached."""
    try:
        run_module.delay(run.pk)
        return None
    except Exception as exc:  # broker down / not configured
        ModuleRun.objects.filter(pk=run.pk, status="queued").update(
            status="failed", finished=timezone.now(),
            error="The analysis queue isn't reachable (is Redis running?). Start it and run the analysis again.")
        return str(exc)
