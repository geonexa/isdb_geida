from django.urls import path

from . import views

urlpatterns = [
    path("datasets/", views.datasets),
    path("modules/", views.modules),
    path("runs/", views.runs),
    path("runs/<int:run_id>/", views.run_detail),
    path("runs/<int:run_id>/cancel/", views.run_cancel),
    path("runs/<int:run_id>/files/<str:name>", views.run_file),
    path("evidence/", views.evidence_list),
    path("evidence/<int:evidence_id>/<str:action>/", views.evidence_review),
]
