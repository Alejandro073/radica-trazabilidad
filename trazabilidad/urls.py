from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("", views.panel, name="panel"),
    path("salud/", views.salud, name="salud"),
    path("ingresar/", auth_views.LoginView.as_view(), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("cuentas/", views.cuenta_lista, name="cuenta_lista"),
    path("cuentas/nueva/", views.cuenta_nueva, name="cuenta_nueva"),
    path("cuentas/<int:pk>/", views.cuenta_detalle, name="cuenta_detalle"),
    path("cuentas/<int:pk>/estado/", views.cuenta_estado, name="cuenta_estado"),
    path("cuentas/<int:pk>/validar/", views.cuenta_validar, name="cuenta_validar"),
    path("cuentas/<int:pk>/aceptar/", views.cuenta_aceptar, name="cuenta_aceptar"),
    path("cuentas/<int:pk>/soportes/", views.soporte_subir, name="soporte_subir"),
    path("cuentas/<int:pk>/glosas/", views.glosa_nueva, name="glosa_nueva"),
    path("soportes/<int:pk>/descargar/", views.soporte_descargar, name="soporte_descargar"),
    path("glosas/<int:pk>/responder/", views.glosa_responder, name="glosa_responder"),
    path("indicadores/", views.indicadores_vista, name="indicadores"),
]
