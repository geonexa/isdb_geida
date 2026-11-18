"""Celery task: generate a report version (same queue as analyses)."""
import logging
import shutil

from celery import shared_task
from django.utils import timezone

from .models import ReportVersion

log = logging.getLogger(__name__)
PDF_URL = "__GEIDA_PDF_URL__"          # replaced when the stored page is served (member or share link)


def generate_now(version):
    """Build the version's web page and PDF (in this process)."""
    from . import render, snapshot
    report = version.report
    folder = version.folder
    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    ctx = snapshot.build(report, version.created_by)
    version.html_path.write_text(render.render_html(ctx, mode="web", pdf_url=PDF_URL), encoding="utf-8")
    pages = render.write_pdf(ctx, version.pdf_path)
    size = sum(f.stat().st_size for f in folder.iterdir() if f.is_file())
    ReportVersion.objects.filter(pk=version.pk).update(
        status="done", snapshot=snapshot.frozen(ctx), pages=pages, size_bytes=size, finished=timezone.now(), error="")


@shared_task(bind=True, name="reports.generate")
def generate(self, version_id):
    if not ReportVersion.objects.filter(pk=version_id, status="queued").update(status="building"):
        return
    v = ReportVersion.objects.select_related("report", "report__project", "report__project__area",
                                             "report__author", "created_by").get(pk=version_id)
    try:
        generate_now(v)
    except Exception as exc:  # noqa: BLE001 - recorded on the version, shown in the Reports tab
        log.exception("Report version %s failed", version_id)
        ReportVersion.objects.filter(pk=version_id).update(status="failed", finished=timezone.now(),
                                                           error=f"The report couldn't be generated: {exc}")


def enqueue(version):
    try:
        generate.delay(version.pk)
        return None
    except Exception as exc:  # broker down / not configured
        ReportVersion.objects.filter(pk=version.pk, status="queued").update(
            status="failed", finished=timezone.now(),
            error="The processing queue isn't reachable (is Redis running?). Start it and generate again.")
        return str(exc)
