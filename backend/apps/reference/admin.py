from django.contrib import admin

from .models import ReferenceDataset


@admin.register(ReferenceDataset)
class ReferenceDatasetAdmin(admin.ModelAdmin):
    list_display = ("dataset", "catalog", "version", "status", "rows", "table", "loaded", "loaded_by")
    list_filter = ("catalog", "status", "dataset")
    search_fields = ("dataset", "title", "folder")
    readonly_fields = [f.name for f in ReferenceDataset._meta.fields]
