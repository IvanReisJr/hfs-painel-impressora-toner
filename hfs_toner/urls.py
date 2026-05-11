"""URL configuration for HFS Painel Impressora Toner."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("printers.urls")),
]
