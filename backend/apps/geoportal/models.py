from django.conf import settings
from django.contrib.gis.db import models


class ProjectArea(models.Model):
    """A project area (AOI) a user saved from the Geo-Portal. Stored in PostGIS (EPSG:4326)."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_areas")
    name = models.CharField(max_length=120)
    country_iso = models.CharField("country (ISO code)", max_length=3, blank=True)
    country_name = models.CharField("country", max_length=120, blank=True)
    geom = models.MultiPolygonField("boundary", srid=4326)
    area_km2 = models.FloatField("area (km²)", default=0)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated"]
        verbose_name = "project area"

    def __str__(self):
        return self.name
