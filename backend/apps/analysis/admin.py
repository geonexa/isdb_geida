from django.contrib import admin

from .models import Evidence, Module, ModuleRun


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "version", "status", "active", "synced")


@admin.register(ModuleRun)
class ModuleRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "module", "phase", "status", "created", "finished")
    list_filter = ("status", "module", "phase")
    readonly_fields = ("log", "error", "outputs", "datasets")


@admin.register(Evidence)
class EvidenceAdmin(admin.ModelAdmin):
    list_display = ("project", "cri_code", "label", "value", "unit", "role", "status", "created")
    list_filter = ("status", "role", "cri_code")
