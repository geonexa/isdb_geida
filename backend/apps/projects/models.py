from django.conf import settings
from django.contrib.gis.db import models

from . import choices as C


class CRI(models.Model):
    """An IsDB Core Result Indicator (library seeded from isdb_cri_2025_seed.csv)."""

    code = models.CharField(max_length=10, primary_key=True)
    group_no = models.PositiveSmallIntegerField()
    group_name = models.CharField(max_length=200)
    name = models.CharField(max_length=300)
    unit = models.CharField(max_length=60, blank=True)
    per_annum = models.BooleanField(default=False)
    sex_disaggregated = models.CharField(max_length=12, default="no")  # yes | no | to_confirm
    geida_role = models.CharField(max_length=12, choices=C.GEO_ROLES, default="none")
    candidate_module = models.CharField(max_length=300, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    library_version = models.CharField(max_length=80, blank=True)
    sort_key = models.FloatField(default=0)

    class Meta:
        ordering = ["group_no", "sort_key"]
        verbose_name = "core result indicator"

    def __str__(self):
        return f"{self.code} {self.name}"


class Project(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=300)
    country_iso3 = models.CharField("country (ISO3)", max_length=3)
    country_name = models.CharField("country", max_length=120)
    sector = models.CharField(max_length=20, choices=C.SECTORS, blank=True)
    stage = models.CharField("cycle stage", max_length=8, choices=C.STAGES, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField("expected completion", null=True, blank=True)
    otl = models.CharField("operations team leader", max_length=160, blank=True)
    hub = models.CharField("regional hub", max_length=20, choices=C.HUBS, blank=True)
    location = models.CharField("location (as described)", max_length=400, blank=True)
    themes = models.JSONField(default=list, blank=True)
    components = models.JSONField(default=list, blank=True)  # [{name, description}]

    status = models.CharField(max_length=10, choices=C.STATUSES, default="draft", db_index=True)
    source = models.CharField(max_length=10, choices=C.SOURCES, default="manual")
    source_info = models.JSONField(default=dict, blank=True)  # e.g. form submitter, import file
    review_comment = models.TextField(blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="projects")
    submitted_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]

    def __str__(self):
        return f"{self.code} {self.title}"


class ProjectArea(models.Model):
    """The project's area of influence (EPSG:4326)."""

    project = models.OneToOneField(Project, on_delete=models.CASCADE, related_name="area")
    method = models.CharField(max_length=10, choices=C.AREA_METHODS)
    geom = models.MultiPolygonField(srid=4326)
    area_km2 = models.FloatField(default=0)
    notes = models.JSONField(default=list, blank=True)  # validation messages shown to the user
    source_name = models.CharField(max_length=255, blank=True)  # uploaded file name
    admin_gids = models.JSONField(default=list, blank=True)
    buffer = models.JSONField(default=dict, blank=True)  # {lon, lat, km}
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "project area of influence"


class Indicator(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="indicators")
    order = models.PositiveSmallIntegerField(default=0)
    level = models.CharField(max_length=10, choices=C.LEVELS, default="output")
    statement = models.CharField(max_length=500)
    unit = models.CharField(max_length=60, blank=True)
    cri = models.ForeignKey(CRI, null=True, blank=True, on_delete=models.PROTECT)
    tier = models.CharField(max_length=20, choices=C.TIERS, default="project_specific")
    baseline_value = models.FloatField(null=True, blank=True)
    baseline_year = models.PositiveSmallIntegerField(null=True, blank=True)
    target_value = models.FloatField(null=True, blank=True)
    target_year = models.PositiveSmallIntegerField(null=True, blank=True)
    means_of_verification = models.CharField(max_length=500, blank=True)
    sex_disaggregated = models.BooleanField(default=False)
    geo_role = models.CharField("geospatial role", max_length=10, choices=C.GEO_ROLES, default="none")

    class Meta:
        ordering = ["order", "id"]


class ProjectDocument(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="documents")
    doc_type = models.CharField(max_length=10, choices=C.DOC_TYPES, default="other")
    title = models.CharField(max_length=255, blank=True)
    url = models.URLField(max_length=1000)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class ProjectLog(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="log")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=40)
    detail = models.JSONField(default=dict, blank=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created"]
