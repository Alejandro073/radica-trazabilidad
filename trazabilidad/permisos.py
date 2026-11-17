from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from .models import Rol


def rol_de(user):
    """Rol efectivo del usuario (los superusuarios sin perfil son administradores)."""
    if not user.is_authenticated:
        return None
    perfil = getattr(user, "perfil", None)
    if perfil is not None:
        return perfil.rol
    return Rol.ADMINISTRADOR if user.is_superuser else Rol.ADMISION


def rol_requerido(*roles):
    """Exige sesión iniciada y que el rol esté entre los permitidos (RF-08)."""

    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            if roles and rol_de(request.user) not in roles:
                raise PermissionDenied
            return vista(request, *args, **kwargs)

        return envoltura

    return decorador
