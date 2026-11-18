from django.contrib import admin

from .models import Report, ReportVersion


class VersionInline(admin.TabularInline):
    model = ReportVersion
    fields = ("number", "status", "pages", "size_bytes", "created_by", "created", "finished")
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "author", "updated")
    search_fields = ("title", "project__code")
    inlines = [VersionInline]
