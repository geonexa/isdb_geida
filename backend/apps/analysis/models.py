from django.conf import settings
from django.db import models

PHASES = [("preparation", "Preparation"), ("implementation", "Implementation"), ("completion", "Completion")]
# Project-cycle instrument each phase reports into.
PHASE_INSTRUMENT = {"preparation": "PPRR", "implementation": "PIASR", "completion": "PCR"}
RUN_STATUS = [("queued", "Queued"), ("running", "Running"), ("done", "Done"), ("failed", "Failed"), ("cancelled", "Cancelled")]
EVIDENCE_STATUS = [("proposed", "Proposed"), ("accepted", "Accepted"), ("rejected", "Rejected")]


class Module(models.Model):
    """An analysis module, synced from modules/<id>/manifest.yaml (the manifest is the source of truth)."""

    id = models.CharField(max_length=60, primary_key=True)
    version = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    question = models.CharField(max_length=400, blank=True)
    status = models.CharField(max_length=20, default="curated")  # curated | experimental
    manifest = models.JSONField(default=dict)
    active = models.BooleanField(default=True)
    synced = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return f"{self.id} {self.version}"


class ModuleRun(models.Model):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="runs")
    module = models.ForeignKey(Module, on_delete=models.PROTECT, related_name="runs")
    module_version = models.CharField(max_length=20)
    phase = models.CharField(max_length=20, choices=PHASES)
    params = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=RUN_STATUS, default="queued", db_index=True)
    progress = models.PositiveSmallIntegerField(default=0)  # 0-100
    log = models.TextField(blank=True)
    error = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    outputs = models.JSONField(default=list, blank=True)  # [{type, name, title, file?, data?, ...}]
    datasets = models.JSONField(default=list, blank=True)  # [{id, title, version, citation, source}]
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, blank=True)
    finished = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created"]

    @property
    def workdir(self):
        return settings.MEDIA_ROOT / "runs" / str(self.pk)


class Evidence(models.Model):
    """A value produced by a module run for a project indicator (CRI), kept with its method and data."""

    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="evidence")
    run = models.ForeignKey(ModuleRun, on_delete=models.CASCADE, related_name="evidence")
    indicator = models.ForeignKey("projects.Indicator", null=True, blank=True, on_delete=models.SET_NULL,
                                  related_name="evidence")
    cri_code = models.CharField(max_length=10, blank=True)
    phase = models.CharField(max_length=20, choices=PHASES)
    instrument = models.CharField(max_length=8)
    label = models.CharField(max_length=300)
    value = models.FloatField(null=True, blank=True)
    unit = models.CharField(max_length=60, blank=True)
    value_male = models.FloatField(null=True, blank=True)
    value_female = models.FloatField(null=True, blank=True)
    reference_date = models.CharField(max_length=40, blank=True)  # date of the data, e.g. "2020" or "2021-06"
    role = models.CharField(max_length=10)  # measure | estimate | verify | context | recorded
    method = models.JSONField(default=dict)  # {module, version, params}
    data = models.JSONField(default=list)  # datasets with versions and citations
    caveats = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=EVIDENCE_STATUS, default="proposed", db_index=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
        verbose_name_plural = "evidence"
