from datetime import date, timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from trazabilidad import services
from trazabilidad.models import CausalGlosa, Estado, EventoTrazabilidad, Resultado, Rol, TipoEvento

from .base import BaseTest


def pdf(nombre="soporte.pdf"):
    return SimpleUploadedFile(nombre, b"%PDF-1.4 prueba", content_type="application/pdf")


class FlujoTest(BaseTest):
    def avanzar_hasta_validacion(self, cuenta):
        adm, fac = self.u[Rol.ADMISION], self.u[Rol.FACTURACION]
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, adm)
        services.cambiar_estado(cuenta, Estado.EGRESADA, adm)
        cuenta.refresh_from_db()
        return services.cambiar_estado(cuenta, Estado.EN_VALIDACION, fac)

    def test_flujo_completo_deja_trazabilidad(self):
        adm, fac, aud = self.u[Rol.ADMISION], self.u[Rol.FACTURACION], self.u[Rol.AUDITORIA]
        cuenta = self.crear_cuenta()
        services.registrar_evento(cuenta, adm, TipoEvento.CREACION, "creada", "", Estado.ADMITIDA)
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, adm)
        services.cambiar_estado(cuenta, Estado.EGRESADA, adm)
        cuenta.refresh_from_db()
        self.assertIsNotNone(cuenta.atencion.fecha_egreso)
        services.cargar_soporte(cuenta, self.hc, pdf(), adm)
        services.cargar_soporte(cuenta, self.fac, pdf("f.pdf"), fac)
        services.cambiar_estado(cuenta, Estado.EN_VALIDACION, fac)
        cuenta.refresh_from_db()
        cuenta, ok, _ = services.validar_documental(cuenta, fac)
        self.assertTrue(ok)
        self.assertEqual(cuenta.estado, Estado.LISTA)
        cuenta = services.cambiar_estado(cuenta, Estado.RADICADA, fac)
        self.assertIsNotNone(cuenta.fecha_radicacion)
        services.agregar_glosa(cuenta, CausalGlosa.SOPORTES, 250_000, "Falta soporte", aud)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.estado, Estado.RESULTADO)
        self.assertEqual(cuenta.resultado, Resultado.GLOSADA)
        tipos = list(cuenta.eventos.values_list("tipo", flat=True))
        self.assertEqual(tipos[0], TipoEvento.CREACION)
        self.assertIn(TipoEvento.RADICACION, tipos)
        self.assertEqual(tipos[-1], TipoEvento.GLOSA)

    def test_rol_no_autorizado(self):
        cuenta = self.crear_cuenta()
        with self.assertRaises(ValidationError):
            services.cambiar_estado(cuenta, Estado.EN_ATENCION, self.u[Rol.FACTURACION])

    def test_administrador_puede_todo(self):
        cuenta = self.crear_cuenta()
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, self.u[Rol.ADMINISTRADOR])

    def test_no_se_permiten_saltos(self):
        cuenta = self.crear_cuenta()
        with self.assertRaises(ValidationError):
            services.cambiar_estado(cuenta, Estado.RADICADA, self.u[Rol.ADMINISTRADOR])

    def test_validacion_incompleta_devuelve_a_egresada(self):
        cuenta = self.avanzar_hasta_validacion(self.crear_cuenta())
        services.cargar_soporte(cuenta, self.hc, pdf(), self.u[Rol.FACTURACION])
        cuenta, ok, detalle = services.validar_documental(cuenta, self.u[Rol.FACTURACION])
        self.assertFalse(ok)
        self.assertEqual(cuenta.estado, Estado.EGRESADA)
        self.assertIn("Factura de venta", detalle)

    def test_sin_reglas_nunca_es_completa(self):
        cuenta = self.crear_cuenta(servicio="consulta")
        est = services.estado_soportes(cuenta)
        self.assertTrue(est["sin_reglas"])
        self.assertFalse(est["completo"])

    def test_desde_validacion_no_se_cambia_a_mano(self):
        cuenta = self.avanzar_hasta_validacion(self.crear_cuenta())
        with self.assertRaises(ValidationError):
            services.cambiar_estado(cuenta, Estado.LISTA, self.u[Rol.FACTURACION])

    def test_formato_de_soporte_invalido(self):
        cuenta = self.crear_cuenta()
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, self.u[Rol.ADMISION])
        cuenta.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.cargar_soporte(cuenta, self.hc, pdf("virus.exe"), self.u[Rol.ADMISION])

    @override_settings(MAX_TAMANO_SOPORTE_MB=0)
    def test_tamano_de_soporte_excedido(self):
        cuenta = self.crear_cuenta()
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, self.u[Rol.ADMISION])
        cuenta.refresh_from_db()
        with self.assertRaises(ValidationError):
            services.cargar_soporte(cuenta, self.hc, pdf(), self.u[Rol.ADMISION])

    def test_no_se_carga_soporte_en_cuenta_radicada(self):
        cuenta = self.crear_cuenta()
        cuenta.estado = Estado.RADICADA
        cuenta.save()
        with self.assertRaises(ValidationError):
            services.cargar_soporte(cuenta, self.hc, pdf(), self.u[Rol.FACTURACION])

    def test_aceptar_cuenta(self):
        cuenta = self.crear_cuenta()
        cuenta.estado = Estado.RADICADA
        cuenta.save()
        cuenta = services.aceptar_cuenta(cuenta, self.u[Rol.AUDITORIA])
        self.assertEqual(cuenta.resultado, Resultado.ACEPTADA)
        with self.assertRaises(ValidationError):
            services.agregar_glosa(cuenta, CausalGlosa.TARIFAS, 1, "", self.u[Rol.AUDITORIA])

    def test_glosa_solo_en_cuenta_radicada(self):
        cuenta = self.crear_cuenta()
        with self.assertRaises(ValidationError):
            services.agregar_glosa(cuenta, CausalGlosa.TARIFAS, 1000, "", self.u[Rol.AUDITORIA])

    def test_responder_glosa(self):
        cuenta = self.crear_cuenta()
        cuenta.estado = Estado.RADICADA
        cuenta.save()
        glosa = services.agregar_glosa(cuenta, CausalGlosa.TARIFAS, 1000, "x", self.u[Rol.FACTURACION])
        services.responder_glosa(glosa, "Se adjunta contrato", self.u[Rol.FACTURACION])
        glosa.refresh_from_db()
        self.assertTrue(glosa.respondida)
        with self.assertRaises(ValidationError):
            services.responder_glosa(glosa, "otra vez", self.u[Rol.FACTURACION])


class PlazosTest(BaseTest):
    def test_dias_habiles(self):
        lunes = date(2026, 11, 2)
        self.assertEqual(services.dias_habiles(lunes, date(2026, 11, 6)), 4)
        self.assertEqual(services.dias_habiles(lunes, date(2026, 11, 9)), 5)
        self.assertEqual(services.dias_habiles(date(2026, 11, 7), date(2026, 11, 8)), 0)
        self.assertEqual(services.dias_habiles(lunes, lunes), 0)
        self.assertEqual(services.dias_habiles(None, lunes), 0)

    def _hoy_con(self, egreso, habiles):
        dia = egreso
        while services.dias_habiles(egreso, dia) < habiles:
            dia += timedelta(days=1)
        return dia

    def test_alerta_de_plazo(self):
        cuenta = self.crear_cuenta()
        cuenta.estado = Estado.EGRESADA
        cuenta.save()
        egreso = date(2026, 10, 1)
        cuenta.atencion.fecha_egreso = egreso
        cuenta.atencion.save()
        self.assertIsNone(services.alerta_plazo(cuenta, self._hoy_con(egreso, 16)))
        self.assertEqual(services.alerta_plazo(cuenta, self._hoy_con(egreso, 17)), "por_vencer")
        self.assertEqual(services.alerta_plazo(cuenta, self._hoy_con(egreso, 22)), "por_vencer")
        self.assertEqual(services.alerta_plazo(cuenta, self._hoy_con(egreso, 23)), "vencida")

    def test_sin_alerta_si_ya_radicada(self):
        cuenta = self.crear_cuenta()
        cuenta.estado = Estado.RADICADA
        cuenta.save()
        cuenta.atencion.fecha_egreso = date(2026, 1, 5)
        cuenta.atencion.save()
        self.assertIsNone(services.alerta_plazo(cuenta, date(2026, 11, 1)))


class InmutabilidadTest(BaseTest):
    def setUp(self):
        self.cuenta = self.crear_cuenta()
        self.evento = services.registrar_evento(
            self.cuenta, self.u[Rol.ADMISION], TipoEvento.CREACION, "x", "", Estado.ADMITIDA
        )

    def test_no_se_modifica(self):
        self.evento.detalle = "alterado"
        with self.assertRaises(PermissionDenied):
            self.evento.save()

    def test_no_se_elimina(self):
        with self.assertRaises(PermissionDenied):
            self.evento.delete()

    def test_consultas_masivas_bloqueadas(self):
        with self.assertRaises(PermissionDenied):
            EventoTrazabilidad.objects.all().update(detalle="x")
        with self.assertRaises(PermissionDenied):
            EventoTrazabilidad.objects.all().delete()
        self.assertEqual(EventoTrazabilidad.objects.count(), 1)
