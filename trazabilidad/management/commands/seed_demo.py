"""Carga datos SINTÉTICOS de demostración (no son datos reales de Corposalud).

Las tasas de glosa imitan el orden de magnitud observado en el diagnóstico
(Emssanar ≈ 12,8 %, Sanitas ≈ 34,8 %, otras ≈ 20 %) para que los indicadores
tengan sentido en la demostración. El generador usa semilla fija (2026).
"""
import os
import random
from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from trazabilidad.models import (
    Atencion,
    CausalGlosa,
    CuentaMedica,
    EntidadPagadora,
    Estado,
    EventoTrazabilidad,
    Glosa,
    ReglaSoporte,
    Resultado,
    Rol,
    SoporteCargado,
    TipoEvento,
    TipoServicio,
    TipoSoporte,
)

ENTIDADES = [
    ("Emssanar EPS", "901021565", 0.128),
    ("Sanitas EPS", "800251440", 0.348),
    ("Nueva EPS", "900156264", 0.20),
    ("Asmet Salud EPS", "800140949", 0.20),
    ("SOAT (aseguradoras)", "000000000", 0.20),
]

SOPORTES = {
    "hc": "Historia clínica",
    "epi": "Epicrisis",
    "fac": "Factura de venta",
    "aut": "Autorización",
    "ord": "Orden médica",
    "gas": "Hoja de gastos",
    "ane": "Registro de anestesia",
    "qui": "Descripción quirúrgica",
    "der": "Comprobante de derechos",
}

REGLAS = {
    TipoServicio.HOSPITALIZACION: ["hc", "epi", "fac", "aut", "gas"],
    TipoServicio.URGENCIAS: ["hc", "fac", "ord", "der"],
    TipoServicio.QUIROFANO: ["hc", "fac", "aut", "ane", "qui"],
    TipoServicio.CONSULTA: ["fac", "ord"],
    TipoServicio.APOYO: ["fac", "ord"],
}

# Distribución del estado final de las cuentas sintéticas
ESTADOS_PESO = [
    (Estado.ADMITIDA, 4), (Estado.EN_ATENCION, 8), (Estado.EGRESADA, 10),
    (Estado.EN_VALIDACION, 6), (Estado.LISTA, 5), (Estado.RADICADA, 15), (Estado.RESULTADO, 52),
]
CAUSALES_PESO = [
    (CausalGlosa.SOPORTES, 26), (CausalGlosa.TARIFAS, 24), (CausalGlosa.AUTORIZACIONES, 20),
    (CausalGlosa.FACTURACION, 16), (CausalGlosa.DERECHOS, 9), (CausalGlosa.OTRA, 5),
]
NOMBRES = ["María", "José", "Luz", "Carlos", "Ana", "Jorge", "Sandra", "Luis", "Diana", "Andrés",
           "Paola", "Hernán", "Gloria", "Mario", "Yolanda", "Edgar", "Nelly", "Wilson", "Rosa", "Camilo"]
APELLIDOS = ["Ortiz", "Muñoz", "Burbano", "Chamorro", "Enríquez", "Insuasty", "Cabrera", "Rosero",
             "Guerrero", "Bastidas", "Delgado", "Erazo", "Mora", "Narváez", "Pantoja", "Ceballos"]


def _fecha(d, hora=9, minuto=0):
    return timezone.make_aware(datetime.combine(d, time(hora, minuto)))


def _elegir(rng, pesos):
    total = sum(p for _, p in pesos)
    r = rng.uniform(0, total)
    acum = 0
    for valor, p in pesos:
        acum += p
        if r <= acum:
            return valor
    return pesos[-1][0]


class Command(BaseCommand):
    help = "Carga datos sintéticos de demostración (usuarios, parámetros y cuentas)."

    def add_arguments(self, parser):
        parser.add_argument("--cantidad", type=int, default=120)
        parser.add_argument("--solo-si-vacio", action="store_true", help="No hace nada si ya hay cuentas.")
        parser.add_argument("--reset", action="store_true", help="Borra las cuentas existentes antes de cargar.")

    def handle(self, *args, **opts):
        if opts["solo_si_vacio"] and CuentaMedica.objects.exists():
            self.stdout.write("Ya hay datos; no se carga la demostración.")
            return
        with transaction.atomic():
            if opts["reset"]:
                EventoTrazabilidad.objects.all()._raw_delete(using="default")
                CuentaMedica.objects.all().delete()
                Atencion.objects.all().delete()
            usuarios = self._usuarios()
            entidades = self._parametros()
            n = self._cuentas(opts["cantidad"], usuarios, entidades)
        self.stdout.write(self.style.SUCCESS(f"Demostración lista: {n} cuentas sintéticas."))

    # ------------------------------------------------------------------ usuarios
    def _usuarios(self):
        User = get_user_model()
        clave = os.environ.get("DEMO_PASSWORD", "Radica2026!")
        definidos = [
            ("admin", Rol.ADMINISTRADOR, True),
            ("admision", Rol.ADMISION, False),
            ("facturacion", Rol.FACTURACION, False),
            ("auditoria", Rol.AUDITORIA, False),
        ]
        salida = {}
        for nombre, rol, staff in definidos:
            user, creado = User.objects.get_or_create(username=nombre)
            if creado:
                user.set_password(clave)
            user.is_staff = staff
            user.is_superuser = staff
            user.save()
            perfil = user.perfil
            perfil.rol = rol
            perfil.save()
            salida[rol] = user
        return salida

    # ---------------------------------------------------------------- parámetros
    def _parametros(self):
        tipos = {k: TipoSoporte.objects.get_or_create(nombre=v)[0] for k, v in SOPORTES.items()}
        entidades = []
        for nombre, nit, tasa in ENTIDADES:
            ent, _ = EntidadPagadora.objects.get_or_create(nombre=nombre, defaults={"nit": nit})
            entidades.append((ent, tasa))
            for servicio, claves in REGLAS.items():
                for k in claves:
                    ReglaSoporte.objects.get_or_create(entidad=ent, tipo_servicio=servicio, tipo_soporte=tipos[k])
        self._tipos = tipos
        return entidades

    # -------------------------------------------------------------------- cuentas
    def _cuentas(self, cantidad, usuarios, entidades):
        rng = random.Random(2026)
        hoy = timezone.localdate()
        u_adm, u_fac, u_aud = usuarios[Rol.ADMISION], usuarios[Rol.FACTURACION], usuarios[Rol.AUDITORIA]
        existentes = CuentaMedica.objects.count()
        servicios = [s for s, _ in TipoServicio.choices]
        for i in range(cantidad):
            ent, tasa = rng.choice(entidades)
            servicio = rng.choice(servicios)
            estado_final = _elegir(rng, ESTADOS_PESO)
            idx = list(Estado.values).index(estado_final)

            ingreso = hoy - timedelta(days=rng.randint(25, 110))
            if estado_final in (Estado.ADMITIDA, Estado.EN_ATENCION):
                ingreso = hoy - timedelta(days=rng.randint(0, 4))
            elif estado_final in (Estado.EGRESADA, Estado.EN_VALIDACION, Estado.LISTA):
                ingreso = hoy - timedelta(days=rng.randint(3, 38))
            egreso = None
            if idx >= 2:
                egreso = min(ingreso + timedelta(days=rng.randint(0, 9)), hoy - timedelta(days=1))
            radicacion = None
            if idx >= 5:
                radicacion = min(egreso + timedelta(days=max(2, int(rng.gauss(7, 3)))), hoy)

            atencion = Atencion.objects.create(
                paciente_documento=str(rng.randint(10_000_000, 1_090_000_000)),
                paciente_nombre=f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}",
                tipo_servicio=servicio, entidad=ent, fecha_ingreso=ingreso,
                fecha_egreso=egreso, creada_por=u_adm,
            )
            cuenta = CuentaMedica.objects.create(
                numero=f"CM-2026-{existentes + i + 1:05d}",
                atencion=atencion,
                valor=rng.randint(15, 1200) * 10_000,
                estado=estado_final,
                fecha_radicacion=radicacion,
                fecha_creacion=_fecha(ingreso, 8, 30),
            )
            self._eventos(cuenta, idx, ingreso, egreso, radicacion, u_adm, u_fac, u_aud, rng)
            self._soportes(cuenta, idx, u_adm, u_fac, rng, ingreso, egreso)
            if idx == 6:
                self._resultado(cuenta, tasa, radicacion, hoy, u_aud, rng)
        return cantidad

    def _eventos(self, cuenta, idx, ingreso, egreso, radicacion, u_adm, u_fac, u_aud, rng):
        def ev(fecha, usuario, tipo, detalle, ant="", nuevo=""):
            EventoTrazabilidad.objects.create(
                cuenta=cuenta, fecha=fecha, usuario=usuario, tipo=tipo,
                detalle=detalle, estado_anterior=ant, estado_nuevo=nuevo,
            )

        ev(_fecha(ingreso, 8, 30), u_adm, TipoEvento.CREACION, "Cuenta médica creada en admisión.", "", Estado.ADMITIDA)
        if idx >= 1:
            ev(_fecha(ingreso, 9, 10), u_adm, TipoEvento.ESTADO, "", Estado.ADMITIDA, Estado.EN_ATENCION)
        if idx >= 2:
            ev(_fecha(egreso, 14, 0), u_adm, TipoEvento.ESTADO, "", Estado.EN_ATENCION, Estado.EGRESADA)
        if idx >= 3:
            ev(_fecha(egreso + timedelta(days=1), 8, 45), u_fac, TipoEvento.ESTADO, "", Estado.EGRESADA, Estado.EN_VALIDACION)
        if idx >= 4:
            ev(_fecha(egreso + timedelta(days=1), 15, 20), u_fac, TipoEvento.VALIDACION,
               "Validación documental superada: soportes completos.", Estado.EN_VALIDACION, Estado.LISTA)
        if idx >= 5:
            ev(_fecha(radicacion, 10, 5), u_fac, TipoEvento.RADICACION, "", Estado.LISTA, Estado.RADICADA)

    def _soportes(self, cuenta, idx, u_adm, u_fac, rng, ingreso, egreso):
        if idx < 1:
            return
        reglas = list(ReglaSoporte.objects.filter(
            entidad=cuenta.atencion.entidad, tipo_servicio=cuenta.atencion.tipo_servicio
        ).select_related("tipo_soporte"))
        for r in reglas:
            # Las cuentas aún en curso (EN_ATENCION / EGRESADA / EN_VALIDACION) pueden estar incompletas.
            if idx in (1, 2, 3) and rng.random() < 0.35:
                continue
            fecha = _fecha(egreso or ingreso, 11, rng.randint(0, 59))
            SoporteCargado.objects.create(
                cuenta=cuenta, tipo=r.tipo_soporte, cargado_por=u_adm if rng.random() < .6 else u_fac,
                nombre_archivo=f"{r.tipo_soporte.nombre.lower().replace(' ', '_')}_{cuenta.numero}.pdf",
                fecha=fecha,
            )

    def _resultado(self, cuenta, tasa, radicacion, hoy, u_aud, rng):
        resp = min(radicacion + timedelta(days=rng.randint(20, 60)), hoy)
        glosada = rng.random() < tasa
        cuenta.resultado = Resultado.GLOSADA if glosada else Resultado.ACEPTADA
        cuenta.save(update_fields=["resultado"])
        if glosada:
            for _ in range(rng.choice([1, 1, 2])):
                valor = int(cuenta.valor * rng.uniform(0.08, 0.6) / 1000) * 1000
                respondida = rng.random() < 0.6
                g = Glosa.objects.create(
                    cuenta=cuenta, causal=_elegir(rng, CAUSALES_PESO), valor_glosado=valor,
                    descripcion="Glosa sintética de demostración.", fecha=resp,
                    respondida=respondida,
                    respuesta="Se allegan soportes y se solicita levantar la glosa." if respondida else "",
                    fecha_respuesta=min(resp + timedelta(days=rng.randint(3, 15)), hoy) if respondida else None,
                )
            detalle, tipo = "Glosa registrada por la entidad.", TipoEvento.GLOSA
        else:
            detalle, tipo = "Cuenta aceptada por la entidad.", TipoEvento.ESTADO
        EventoTrazabilidad.objects.create(
            cuenta=cuenta, fecha=_fecha(resp, 16, 0), usuario=u_aud, tipo=tipo,
            detalle=detalle, estado_anterior=Estado.RADICADA, estado_nuevo=Estado.RESULTADO,
        )
