from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Radica · Administración"
admin.site.site_title = "Radica"
admin.site.index_title = "Usuarios, roles y parámetros de soportes"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("trazabilidad.urls")),
]
