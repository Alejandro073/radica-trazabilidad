from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import (
    Atencion,
    CuentaMedica,
    EntidadPagadora,
    EventoTrazabilidad,
    Glosa,
    Perfil,
    ReglaSoporte,
    SoporteCargado,
    TipoSoporte,
)


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    extra = 0


class UsuarioAdmin(UserAdmin):
    inlines = [PerfilInline]
    list_display = ("username", "first_name", "last_name", "rol", "is_active")

    def get_inline_instances(self, request, obj=None):
        # Al crear el usuario, una señal genera el perfil; el rol se edita después.
        return super().get_inline_instances(request, obj) if obj else []

    @admin.display(description="Rol")
    def rol(self, obj):
        return getattr(getattr(obj, "perfil", None), "rol", "—")


admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)


@admin.register(EntidadPagadora)
class EntidadAdmin(admin.ModelAdmin):
    list_display = ("nombre", "nit", "plazo_radicacion_dias", "activa")
    list_filter = ("activa",)
    search_fields = ("nombre", "nit")


@admin.register(TipoSoporte)
class TipoSoporteAdmin(admin.ModelAdmin):
    search_fields = ("nombre",)


@admin.register(ReglaSoporte)
class ReglaSoporteAdmin(admin.ModelAdmin):
    list_display = ("entidad", "tipo_servicio", "tipo_soporte")
    list_filter = ("entidad", "tipo_servicio")


class SoporteInline(admin.TabularInline):
    model = SoporteCargado
    extra = 0


@admin.register(CuentaMedica)
class CuentaAdmin(admin.ModelAdmin):
    list_display = ("numero", "atencion", "estado", "resultado", "valor", "fecha_radicacion")
    list_filter = ("estado", "resultado")
    search_fields = ("numero", "atencion__paciente_documento", "atencion__paciente_nombre")
    inlines = [SoporteInline]


admin.site.register(Atencion)
admin.site.register(Glosa)


@admin.register(EventoTrazabilidad)
class EventoAdmin(admin.ModelAdmin):
    """Solo lectura: la trazabilidad no se edita ni se elimina desde ningún sitio."""

    list_display = ("fecha", "cuenta", "tipo", "usuario", "estado_nuevo")
    list_filter = ("tipo",)
    search_fields = ("cuenta__numero",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
