from django.urls import path

from . import views

urlpatterns = [
    path("units/", views.unit_list),
    path("units/geojson/", views.unit_geojson),
    path("units/<str:gid>/", views.unit_detail),
    path("world/", views.world),
    path("at/", views.units_at),
    path("union/", views.units_union),
]
