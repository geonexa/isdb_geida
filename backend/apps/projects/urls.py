from django.urls import path

from apps.geoportal import project_rs

from . import importer, views

urlpatterns = [
    path("", views.project_list),
    path("meta/", views.meta),
    path("cri/", views.cri_search),
    path("area/preview/", views.area_preview),
    path("import/template/", importer.template),
    path("import/preview/", importer.preview),
    path("import/commit/", importer.commit),
    path("<str:code>/", views.project_detail_view),
    path("<str:code>/area/", views.project_area),
    path("<str:code>/indicators/", views.project_indicators),
    path("<str:code>/documents/", views.project_documents),
    path("<str:code>/satellite/", project_rs.satellite_list),
    path("<str:code>/satellite/<slug:layer_id>/tiles/", project_rs.satellite_tiles),
    path("<str:code>/satellite/<slug:layer_id>/xyz/<int:z>/<int:x>/<int:y>.png", project_rs.satellite_xyz),
    path("<str:code>/satellite/<slug:layer_id>/download/", project_rs.satellite_download),
    path("<str:code>/<str:action>/", views.project_action),
]
