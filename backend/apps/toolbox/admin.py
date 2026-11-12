from django.contrib import admin

from .models import ToolRun, ToolUpload


@admin.register(ToolRun)
class ToolRunAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "tool", "name", "status", "created_by", "created", "size_bytes")
    list_filter = ("status", "tool")
    search_fields = ("project__code", "name", "tool")


@admin.register(ToolUpload)
class ToolUploadAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "name", "kind", "created_by", "created", "size_bytes")
