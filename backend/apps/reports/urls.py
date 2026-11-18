from django.urls import path

from . import views

urlpatterns = [
    path("versions/<int:version_id>/", views.version_html),
    path("versions/<int:version_id>/pdf", views.version_pdf),
    path("shared/<str:token>/", views.shared_html),
    path("shared/<str:token>/pdf", views.shared_pdf),
    path("<int:report_id>/", views.report_detail),
    path("<int:report_id>/preview/", views.report_preview),
    path("<int:report_id>/generate/", views.report_generate),
    path("<int:report_id>/share/", views.report_share),
    path("<str:code>/runs/", views.project_runs),
    path("<str:code>/", views.project_reports),
]
