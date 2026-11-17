"""Indicadores de gestión (RF-09): glosas, tiempos y cumplimiento del plazo."""
from collections import OrderedDict

from django.db.models import Count, Sum

from .models import CausalGlosa, CuentaMedica, EntidadPagadora, Estado, Glosa, Resultado
from .services import dias_habiles

ESTADOS_RADICADOS = (Estado.RADICADA, Estado.RESULTADO)


def _pct(parte, total):
    return round(parte * 100 / total, 1) if total else 0.0


def conteo_por_estado():
    cuentas = dict(CuentaMedica.objects.values_list("estado").annotate(n=Count("id")))
    return OrderedDict((valor, (etiqueta, cuentas.get(valor, 0))) for valor, etiqueta in Estado.choices)


def resumen_glosas(entidad=None):
    base = CuentaMedica.objects.filter(estado__in=ESTADOS_RADICADOS)
    glosas = Glosa.objects.all()
    if entidad is not None:
        base = base.filter(atencion__entidad=entidad)
        glosas = glosas.filter(cuenta__atencion__entidad=entidad)
    radicadas = base.count()
    glosadas = base.filter(resultado=Resultado.GLOSADA).count()
    valor_rad = base.aggregate(s=Sum("valor"))["s"] or 0
    valor_glo = glosas.aggregate(s=Sum("valor_glosado"))["s"] or 0
    return {
        "radicadas": radicadas,
        "glosadas": glosadas,
        "pct_cuentas": _pct(glosadas, radicadas),
        "valor_radicado": int(valor_rad),
        "valor_glosado": int(valor_glo),
        "pct_valor": _pct(valor_glo, valor_rad),
    }


def tiempo_promedio_radicacion():
    """Promedio de días calendario entre egreso y radicación, y % dentro del plazo."""
    cuentas = CuentaMedica.objects.filter(
        fecha_radicacion__isnull=False, atencion__fecha_egreso__isnull=False
    ).select_related("atencion__entidad")
    dias = []
    en_plazo = 0
    for c in cuentas:
        egreso = c.atencion.fecha_egreso
        dias.append((c.fecha_radicacion - egreso).days)
        if dias_habiles(egreso, c.fecha_radicacion) <= c.atencion.entidad.plazo_radicacion_dias:
            en_plazo += 1
    n = len(dias)
    return {
        "n": n,
        "promedio_dias": round(sum(dias) / n, 1) if n else 0.0,
        "pct_en_plazo": _pct(en_plazo, n),
    }


def causas_de_glosa():
    filas = Glosa.objects.values("causal").annotate(n=Count("id"), valor=Sum("valor_glosado"))
    etiquetas = dict(CausalGlosa.choices)
    total = sum(f["n"] for f in filas) or 0
    salida = [
        {
            "causal": etiquetas.get(f["causal"], f["causal"]),
            "n": f["n"],
            "valor": int(f["valor"] or 0),
            "pct": _pct(f["n"], total),
        }
        for f in filas
    ]
    return sorted(salida, key=lambda x: -x["n"])


def por_entidad():
    filas = []
    for ent in EntidadPagadora.objects.filter(activa=True):
        r = resumen_glosas(ent)
        if r["radicadas"]:
            filas.append({"entidad": ent.nombre, **r})
    return sorted(filas, key=lambda x: -x["pct_cuentas"])


def todos():
    return {
        "estados": conteo_por_estado(),
        "glosas": resumen_glosas(),
        "tiempos": tiempo_promedio_radicacion(),
        "causas": causas_de_glosa(),
        "entidades": por_entidad(),
    }
