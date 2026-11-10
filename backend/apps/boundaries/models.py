from django.contrib.gis.db import models


class AdminUnit(models.Model):
    """An administrative unit (GADM 4.1, levels 0-3) of an IsDB member country.

    `geom` is full resolution (analysis, clipping, area of influence); `geom_display`
    is simplified with shared edges kept (map display and the admin-unit picker).
    """

    gid = models.CharField("GADM id", max_length=40, unique=True)
    level = models.PositiveSmallIntegerField(db_index=True)
    iso3 = models.CharField("country (ISO3)", max_length=3, db_index=True)
    country = models.CharField(max_length=120)
    name = models.CharField(max_length=160, db_index=True)
    name_local = models.CharField("local name", max_length=200, blank=True)
    type = models.CharField(max_length=80, blank=True)
    parent_gid = models.CharField("parent GADM id", max_length=40, blank=True, db_index=True)
    name_1 = models.CharField(max_length=160, blank=True)
    name_2 = models.CharField(max_length=160, blank=True)
    name_3 = models.CharField(max_length=160, blank=True)
    hasc = models.CharField("HASC code", max_length=40, blank=True)
    disputed = models.BooleanField(default=False)
    area_km2 = models.FloatField("area (km²)", default=0)
    geom = models.MultiPolygonField("boundary", srid=4326)
    geom_display = models.MultiPolygonField("display boundary", srid=4326, null=True, blank=True)

    class Meta:
        ordering = ["iso3", "level", "name"]
        indexes = [models.Index(fields=["iso3", "level"])]
        verbose_name = "admin unit"

    def __str__(self):
        return f"{self.name} ({self.gid})"

    @property
    def path(self):
        """'Country › Province › District' style label."""
        parts = [self.country, self.name_1, self.name_2, self.name_3][: self.level + 1]
        return " › ".join(p for p in parts if p)
