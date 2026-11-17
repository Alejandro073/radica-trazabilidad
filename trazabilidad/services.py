"""Lógica de negocio (capa de aplicación): estados, validación y trazabilidad."""
import os
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import (
    CuentaMedica,
    Estado,
    EventoTrazabilidad,
    Glosa,
    ReglaSoporte,
    Resultado,
    Rol,
    SoporteCargado,
    TipoEvento,
)
from .permisos import rol_de

UMBRAL_ALERTA_DIAS = 17  # alerta temprana: 17 de 22 días hábiles

# estado actual -> {estado destino: roles autorizados}
TRANSICIONES = {
    Estado.ADMITIDA: {Estado.EN_ATENCION: {Rol.ADMISION}},
    Estado.EN_ATENCION: {Estado.EGRESADA: {Rol.ADMISION}},
    Estado.EGRESADA: {Estado.EN_VALIDACION: {Rol.FACTURACION}},
    Estado.EN_VALIDACION: {
        Estado.LISTA: {Rol.FACTURACION},
        Estado.EGRESADA: {Rol.FACTURACION},
    },
    Estado.LISTA: {Estado.RADICADA: {Rol.FACTURACION}},
    Estado.RADICADA: {Estado.RESULTADO: {Rol.FACTURACION, Rol.AUDITORIA}},
}


def _v(x):
    """Valor plano (str) de un miembro de TextChoices o de un str cualquiera."""
    return getattr(x, "value", x)


TRANSICIONES = {
    _v(origen): {_v(d): {_v(r) for r in roles} for d, roles in destinos.items()}
    for origen, destinos in TRANSICIONES.items()
}


def registrar_evento(cuenta, usuario, tipo, detalle="", anterior="", nuevo=""):
    return EventoTrazabilidad.objects.create(
        cuenta=cuenta,
        usuario=usuario,
        tipo=tipo,
        estado_anterior=anterior,
        estado_nuevo=nuevo,
        detalle=detalle[:500],
    )


def dias_habiles(desde, hasta):
    """Días hábiles (lunes a viernes) transcurridos entre dos fechas.

    El prototipo no incluye el calendario de festivos; se documenta como
    limitación y se parametriza en una fase posterior.
    """
    if desde is None or hasta is None or hasta <= desde:
        return 0
    total = 0
    dia = desde
    while dia < hasta:
        dia += timedelta(days=1)
        if dia.weekday() < 5:
            total += 1
    return total


def acciones_disponibles(cuenta, usuario):
    """Estados a los que el usuario puede mover la cuenta ahora."""
    rol = _v(rol_de(usuario))
    destinos = TRANSICIONES.get(_v(cuenta.estado), {})
    return [
        destino
        for destino, roles in destinos.items()
        if rol == Rol.ADMINISTRADOR.value or rol in roles
    ]


def _exigir_rol(cuenta, usuario, destino):
    rol = _v(rol_de(usuario))
    destino = _v(destino)
    roles = TRANSICIONES.get(_v(cuenta.estado), {}).get(destino)
    if roles is None:
        raise ValidationError(
            f"No se permite pasar de «{cuenta.get_estado_display()}» a «{Estado(destino).label}»."
        )
    if rol != Rol.ADMINISTRADOR.value and rol not in roles:
        raise ValidationError("Su rol no está autorizado para esta transición.")


@transaction.atomic
def cambiar_estado(cuenta, destino, usuario, detalle=""):
    """Cambia el estado de la cuenta validando rol y secuencia (RF-02)."""
    cuenta = CuentaMedica.objects.select_for_update().get(pk=cuenta.pk)
    _exigir_rol(cuenta, usuario, destino)
    if cuenta.estado == Estado.EN_VALIDACION:
        raise ValidationError("Desde la validación documental use la acción «Validar documentación».")
    anterior = cuenta.estado
    cuenta.estado = destino
    atencion = cuenta.atencion
    hoy = timezone.localdate()
    if destino == Estado.EGRESADA and atencion.fecha_egreso is None:
        atencion.fecha_egreso = hoy
        atencion.save(update_fields=["fecha_egreso"])
    tipo = TipoEvento.ESTADO
    if destino == Estado.RADICADA:
        cuenta.fecha_radicacion = hoy
        tipo = TipoEvento.RADICACION
    cuenta.save()
    registrar_evento(cuenta, usuario, tipo, detalle, anterior, destino)
    return cuenta


def reglas_de(cuenta):
    """Tipos de soporte obligatorios para la entidad y el servicio de la cuenta."""
    return list(
        ReglaSoporte.objects.filter(
            entidad=cuenta.atencion.entidad, tipo_servicio=cuenta.atencion.tipo_servicio
        ).select_related("tipo_soporte")
    )


def estado_soportes(cuenta):
    """Lista de (tipo, cargado?) y los tipos faltantes.

    Si no hay reglas parametrizadas, la cuenta NO se considera completa: es
    preferible detener la radicación a enviar una cuenta sin criterio de soportes.
    """
    reglas = reglas_de(cuenta)
    cargados = set(cuenta.soportes.values_list("tipo_id", flat=True))
    detalle = [(r.tipo_soporte, r.tipo_soporte_id in cargados) for r in reglas]
    faltantes = [t for t, ok in detalle if not ok]
    return {
        "detalle": detalle,
        "faltantes": faltantes,
        "completo": bool(reglas) and not faltantes,
        "sin_reglas": not reglas,
    }


@transaction.atomic
def validar_documental(cuenta, usuario):
    """Validación documental: pasa a «Lista» o devuelve a «Egresada» (RF-04, RF-05)."""
    cuenta = CuentaMedica.objects.select_for_update().get(pk=cuenta.pk)
    _exigir_rol(cuenta, usuario, Estado.LISTA)
    if cuenta.estado != Estado.EN_VALIDACION:
        raise ValidationError("La cuenta debe estar en validación documental.")
    est = estado_soportes(cuenta)
    anterior = cuenta.estado
    if est["completo"]:
        cuenta.estado = Estado.LISTA
        detalle = "Validación documental superada: soportes completos."
    else:
        cuenta.estado = Estado.EGRESADA
        if est["sin_reglas"]:
            detalle = "Validación fallida: no hay soportes obligatorios parametrizados."
        else:
            detalle = "Validación fallida. Faltan: " + ", ".join(t.nombre for t in est["faltantes"])
    cuenta.save()
    registrar_evento(cuenta, usuario, TipoEvento.VALIDACION, detalle, anterior, cuenta.estado)
    return cuenta, est["completo"], detalle


def _validar_archivo(archivo):
    if archivo is None:
        return
    nombre = (archivo.name or "").lower()
    if not nombre.endswith(tuple(settings.EXTENSIONES_SOPORTE)):
        raise ValidationError("Formato no permitido. Use PDF, PNG o JPG.")
    if archivo.size > settings.MAX_TAMANO_SOPORTE_MB * 1024 * 1024:
        raise ValidationError(f"El archivo supera {settings.MAX_TAMANO_SOPORTE_MB} MB.")


ESTADOS_CARGA = (Estado.EN_ATENCION, Estado.EGRESADA, Estado.EN_VALIDACION)


@transaction.atomic
def cargar_soporte(cuenta, tipo, archivo, usuario):
    """Adjunta un soporte a la cuenta y deja el evento correspondiente (RF-03)."""
    if cuenta.estado not in ESTADOS_CARGA:
        raise ValidationError("En este estado ya no se pueden cargar soportes.")
    rol = rol_de(usuario)
    if rol not in (Rol.ADMISION, Rol.FACTURACION, Rol.ADMINISTRADOR):
        raise ValidationError("Su rol no puede cargar soportes.")
    _validar_archivo(archivo)
    soporte = SoporteCargado(
        cuenta=cuenta,
        tipo=tipo,
        cargado_por=usuario,
        nombre_archivo=os.path.basename(archivo.name) if archivo else "",
    )
    if archivo:
        soporte.archivo = archivo
    soporte.save()
    registrar_evento(cuenta, usuario, TipoEvento.SOPORTE, f"Soporte cargado: {tipo.nombre}")
    return soporte


@transaction.atomic
def agregar_glosa(cuenta, causal, valor, descripcion, usuario):
    """Registra una glosa; la cuenta radicada pasa a «Glosada o aceptada» (RF-07)."""
    if cuenta.estado not in (Estado.RADICADA, Estado.RESULTADO):
        raise ValidationError("Solo se registran glosas en cuentas radicadas.")
    if rol_de(usuario) not in (Rol.FACTURACION, Rol.AUDITORIA, Rol.ADMINISTRADOR):
        raise ValidationError("Su rol no puede registrar glosas.")
    if cuenta.estado == Estado.RESULTADO and cuenta.resultado == Resultado.ACEPTADA:
        raise ValidationError("La cuenta ya fue aceptada sin glosa.")
    if valor is None or valor < 0:
        raise ValidationError("El valor glosado no es válido.")
    glosa = Glosa.objects.create(
        cuenta=cuenta, causal=causal, valor_glosado=valor, descripcion=descripcion
    )
    anterior = cuenta.estado
    cuenta.estado = Estado.RESULTADO
    cuenta.resultado = Resultado.GLOSADA
    cuenta.save(update_fields=["estado", "resultado"])
    registrar_evento(
        cuenta, usuario, TipoEvento.GLOSA,
        f"Glosa por {glosa.get_causal_display().lower()} por ${int(valor):,}".replace(",", "."),
        anterior, cuenta.estado,
    )
    return glosa


@transaction.atomic
def responder_glosa(glosa, respuesta, usuario):
    if rol_de(usuario) not in (Rol.FACTURACION, Rol.AUDITORIA, Rol.ADMINISTRADOR):
        raise ValidationError("Su rol no puede responder glosas.")
    if glosa.respondida:
        raise ValidationError("La glosa ya fue respondida.")
    if not respuesta.strip():
        raise ValidationError("Escriba la respuesta a la glosa.")
    glosa.respondida = True
    glosa.respuesta = respuesta.strip()
    glosa.fecha_respuesta = timezone.localdate()
    glosa.save()
    registrar_evento(glosa.cuenta, usuario, TipoEvento.RESPUESTA, f"Respuesta a glosa ({glosa.get_causal_display()})")
    return glosa


@transaction.atomic
def aceptar_cuenta(cuenta, usuario):
    """La entidad acepta la cuenta sin glosas."""
    if cuenta.estado != Estado.RADICADA:
        raise ValidationError("Solo se puede aceptar una cuenta radicada.")
    cuenta = cambiar_estado(cuenta, Estado.RESULTADO, usuario, "Cuenta aceptada por la entidad.")
    cuenta.resultado = Resultado.ACEPTADA
    cuenta.save(update_fields=["resultado"])
    return cuenta


def alerta_plazo(cuenta, hoy=None):
    """Estado del plazo de radicación: None, 'por_vencer' o 'vencida'."""
    if cuenta.estado in (Estado.ADMITIDA, Estado.EN_ATENCION, Estado.RADICADA, Estado.RESULTADO):
        return None
    egreso = cuenta.atencion.fecha_egreso
    if egreso is None:
        return None
    hoy = hoy or timezone.localdate()
    plazo = cuenta.atencion.entidad.plazo_radicacion_dias
    transcurridos = dias_habiles(egreso, hoy)
    if transcurridos > plazo:
        return "vencida"
    if transcurridos >= min(UMBRAL_ALERTA_DIAS, plazo):
        return "por_vencer"
    return None


def dias_restantes(cuenta, hoy=None):
    egreso = cuenta.atencion.fecha_egreso
    if egreso is None:
        return None
    hoy = hoy or timezone.localdate()
    return cuenta.atencion.entidad.plazo_radicacion_dias - dias_habiles(egreso, hoy)
