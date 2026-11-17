from .models import Rol
from .permisos import rol_de


def contexto_rol(request):
    """Variables de plantilla con el rol del usuario y los accesos del menú."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    rol = rol_de(user)
    return {
        "rol": rol,
        "rol_etiqueta": Rol(rol).label if rol in Rol.values else rol,
        "puede_crear": rol == Rol.ADMISION,
        "puede_ver_indicadores": rol in (Rol.FACTURACION, Rol.AUDITORIA, Rol.ADMINISTRADOR),
        "es_administrador": rol == Rol.ADMINISTRADOR and user.is_staff,
    }
