"""
Project reports: a user picks analysis runs of a project, writes a summary, and generates numbered versions,
each frozen as a self-contained web page and a PDF (media/reports/<report>/v<n>/).
"""
import secrets
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone

STATUS = [("queued", "Queued"), ("building", "Building"), ("done", "Done"), ("failed", "Failed")]
BASEMAPS = [("satellite", "Satellite"), ("light", "Light")]


def report_root():
    return Path(settings.MEDIA_ROOT) / "reports"


def default_content():
    # sections: [{"run": id, "outputs": [names], "note": str}] in report order; options switch sections on or off.
    return {"summary": "", "sections": [], "options": {"project": True, "annex": True, "basemap": "satellite"}}


class Report(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=300, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="reports")
    content = models.JSONField(default=default_content)
    share_token = models.CharField(max_length=64, blank=True, db_index=True)
    share_expires = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]

    def __str__(self):
        return f"{self.project_id}: {self.title}"

    @property
    def folder(self):
        return report_root() / str(self.pk)

    def new_token(self):
        self.share_token = secrets.token_urlsafe(24)
        return self.share_token

    @property
    def share_active(self):
        return bool(self.share_token) and (self.share_expires is None or self.share_expires > timezone.now())

    def latest_done(self):
        return self.versions.filter(status="done").order_by("-number").first()


class ReportVersion(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS, default="queued", db_index=True)
    error = models.TextField(blank=True)
    snapshot = models.JSONField(default=dict, blank=True)   # what the version shows (texts, figures, runs), no images
    pages = models.PositiveIntegerField(default=0)
    size_bytes = models.BigIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-number"]
        unique_together = [("report", "number")]

    def __str__(self):
        return f"{self.report} v{self.number}"

    @property
    def folder(self):
        return self.report.folder / f"v{self.number}"

    @property
    def html_path(self):
        return self.folder / "report.html"

    @property
    def pdf_path(self):
        return self.folder / "report.pdf"
