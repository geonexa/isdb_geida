"""Celery task for Toolbox runs (same queue as analyses)."""
from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.utils import timezone

from .models import ToolRun
from .runner import execute


@shared_task(bind=True, name="toolbox.run_tool")
def run_tool(self, run_id):
    if not ToolRun.objects.filter(pk=run_id, status="queued").update(status="running"):
        return  # deleted, or taken by another worker
    run = ToolRun.objects.select_related("project", "project__area").get(pk=run_id)
    try:
        execute(run)
    except SoftTimeLimitExceeded:
        ToolRun.objects.filter(pk=run_id).update(status="failed", finished=timezone.now(),
                                                 error="The tool took too long and was stopped. Try a smaller input.")


def enqueue(run):
    try:
        run_tool.delay(run.pk)
        return None
    except Exception as exc:  # broker down / not configured
        ToolRun.objects.filter(pk=run.pk, status="queued").update(
            status="failed", finished=timezone.now(),
            error="The processing queue isn't reachable (is Redis running?). Start it and run the tool again.")
        return str(exc)
