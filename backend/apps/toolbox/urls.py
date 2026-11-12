from django.urls import path

from . import views

urlpatterns = [
    path("tools/", views.tools),
    path("runs/delete/", views.runs_delete),
    path("runs/<int:run_id>/", views.run_detail),
    path("runs/<int:run_id>/files/<str:name>", views.run_file),
    path("uploads/<int:upload_id>/", views.upload_detail),
    path("<str:code>/inputs/", views.project_inputs),
    path("<str:code>/runs/", views.project_runs),
    path("<str:code>/uploads/", views.project_uploads),
]
