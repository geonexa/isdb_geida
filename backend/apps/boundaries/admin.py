from django.contrib import admin

from .models import AdminUnit


@admin.register(AdminUnit)
class AdminUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "gid", "level", "type", "iso3", "area_km2", "disputed")
    list_filter = ("level", "iso3", "disputed")
    search_fields = ("name", "gid", "name_1", "name_2", "hasc")
    exclude = ("geom", "geom_display")
    readonly_fields = [f for f in ("gid", "level", "iso3", "country", "parent_gid", "area_km2")]
