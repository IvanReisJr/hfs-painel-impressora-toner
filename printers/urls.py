"""URL patterns for printers app."""

from django.urls import path

from printers import views

app_name = "printers"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("impressora/<int:pk>/", views.printer_detail, name="printer_detail"),
    path("api/status/", views.api_status, name="api_status"),
    path("api/coletar/<int:pk>/", views.api_collect_now, name="api_collect_now"),
]
