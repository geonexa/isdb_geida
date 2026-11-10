from django.contrib.gis import admin

from .models import ProjectArea


@admin.register(ProjectArea)
class ProjectAreaAdmin(admin.GISModelAdmin):
    list_display = ("name", "country_name", "owner", "area_km2", "updated")
    list_filter = ("country_name",)
    search_fields = ("name", "country_name", "owner__email")
    readonly_fields = ("area_km2", "created", "updated")
