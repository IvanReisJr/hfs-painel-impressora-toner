"""URL patterns for printers app."""

from django.urls import path

from printers import views

app_name = "printers"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("impressora/<int:pk>/", views.printer_detail, name="printer_detail"),
    path("api/status/", views.api_status, name="api_status"),
    path("api/coletar/<int:pk>/", views.api_collect_now, name="api_collect_now"),
    path("api/coletar-todos/", views.api_collect_all, name="api_collect_all"),
    path("api/atualizar-localizacoes/", views.api_update_locations, name="api_update_locations"),
    path("api/job-status/", views.api_job_status, name="api_job_status"),
]
