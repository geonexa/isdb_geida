from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin

from .models import CRI, Indicator, MapLayout, MapSettings, MapTemplate, Project, ProjectArea, ProjectDocument, ProjectLog


class IndicatorInline(admin.TabularInline):
    model = Indicator
    extra = 0
    autocomplete_fields = ("cri",)


class DocumentInline(admin.TabularInline):
    model = ProjectDocument
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("code", "title", "country_name", "sector", "stage", "status", "source", "updated")
    list_filter = ("status", "source", "sector", "stage", "country_name")
    search_fields = ("code", "title", "country_name")
    inlines = [IndicatorInline, DocumentInline]


@admin.register(ProjectArea)
class ProjectAreaAdmin(GISModelAdmin):
    list_display = ("project", "method", "area_km2", "updated")


@admin.register(CRI)
class CRIAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "unit", "group_name", "geida_role")
    list_filter = ("group_name", "geida_role")
    search_fields = ("code", "name")


@admin.register(ProjectLog)
class ProjectLogAdmin(admin.ModelAdmin):
    list_display = ("project", "action", "user", "created")
    list_filter = ("action",)


@admin.register(MapTemplate)
class MapTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "saved")
    search_fields = ("name", "user__email")


@admin.register(MapLayout)
class MapLayoutAdmin(admin.ModelAdmin):
    list_display = ("project", "user", "updated")
    search_fields = ("project__code", "user__email")


admin.site.register(MapSettings)
