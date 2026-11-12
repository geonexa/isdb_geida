from pathlib import Path

from django.conf import settings
from django.db import models

STATUS = [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed")]


def tool_root():
    return Path(settings.MEDIA_ROOT) / "tools"


class ToolRun(models.Model):
    """One Toolbox tool run on a project: the tool, its settings and inputs, and the result files it produced."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tool_runs")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="tool_runs")
    tool = models.CharField(max_length=80)            # GeoLibre tool id, or geida_* for GEIDA's own tools
    tool_title = models.CharField(max_length=200)
    engine = models.CharField(max_length=40)          # e.g. "geolibre 1.7.1" or "geida"
    name = models.CharField(max_length=200)           # editable label shown in the results list
    params = models.JSONField(default=dict)           # values typed in the form
    inputs = models.JSONField(default=dict)           # {param: ref or [refs]} (see inputs.py)
    status = models.CharField(max_length=10, choices=STATUS, default="queued", db_index=True)
    error = models.TextField(blank=True)
    log = models.TextField(blank=True)
    outputs = models.JSONField(default=list)          # [{name, title, kind, file, ...}]
    report = models.JSONField(null=True, blank=True)  # what the tool printed as its report (statistics)
    size_bytes = models.BigIntegerField(default=0)
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"#{self.pk} {self.tool} ({self.project_id})"

    @property
    def workdir(self):
        return tool_root() / str(self.pk)


class ToolUpload(models.Model):
    """A file a user added to a project for the Toolbox (vector, raster or table), kept until deleted."""

    KINDS = [("vector", "Vector"), ("raster", "Raster"), ("table", "Table")]
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="tool_uploads")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="tool_uploads")
    name = models.CharField(max_length=200)
    kind = models.CharField(max_length=10, choices=KINDS)
    file = models.CharField(max_length=300)           # path relative to tool_root()/uploads/<id>/
    size_bytes = models.BigIntegerField(default=0)
    info = models.JSONField(default=dict)             # features, geometry, fields / width, height, crs
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]

    @property
    def folder(self):
        return tool_root() / "uploads" / str(self.pk)

    @property
    def path(self):
        return self.folder / self.file
