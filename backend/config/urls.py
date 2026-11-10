from django.contrib import admin
from django.urls import include, path, re_path

from apps.core.api import not_found

admin.site.site_header = "GEIDA administration"
admin.site.site_title = "GEIDA"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/site/", include("apps.core.urls")),
    path("api/geoportal/", include("apps.geoportal.urls")),
    path("api/boundaries/", include("apps.boundaries.urls")),
    path("api/projects/", include("apps.projects.urls")),
    path("api/analysis/", include("apps.analysis.urls")),
    re_path(r"^api/", not_found),  # unknown API paths answer in JSON, not HTML
]
