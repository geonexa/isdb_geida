from django.urls import path

from . import areas, search, views

urlpatterns = [
    path("config/", views.config),
    path("basemaps/", views.basemaps),
    path("layers/<slug:layer_id>/tiles/", views.layer_tiles),
    path("layers/<slug:layer_id>/xyz/<int:z>/<int:x>/<int:y>.png", views.layer_xyz),
    path("layers/<slug:layer_id>/clip/", views.layer_clip),
    path("search/", search.place_search),
    path("areas/", areas.area_list),
    path("areas/<int:area_id>/", areas.area_detail),
]
