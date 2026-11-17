from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from trazabilidad import services
from trazabilidad.models import CuentaMedica, Estado, Rol, TipoEvento

from .base import BaseTest


class AccesoTest(BaseTest):
    def test_requiere_sesion(self):
        r = self.client.get(reverse("panel"))
        self.assertEqual(r.status_code, 302)
        self.assertIn("/ingresar/", r["Location"])

    def test_salud_es_publico(self):
        r = self.client.get(reverse("salud"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_login_y_panel(self):
        r = self.client.post(reverse("login"), {"username": "facturacion", "password": "clave-de-prueba"})
        self.assertRedirects(r, reverse("panel"))
        self.assertEqual(self.client.get(reverse("panel")).status_code, 200)

    def test_todos_los_roles_ven_panel_y_lista(self):
        self.crear_cuenta()
        for rol in Rol.values:
            self.login(rol)
            self.assertEqual(self.client.get(reverse("panel")).status_code, 200, rol)
            self.assertEqual(self.client.get(reverse("cuenta_lista")).status_code, 200, rol)

    def test_permisos_por_rol(self):
        self.login(Rol.AUDITORIA)
        self.assertEqual(self.client.get(reverse("cuenta_nueva")).status_code, 403)
        self.login(Rol.ADMISION)
        self.assertEqual(self.client.get(reverse("indicadores")).status_code, 403)
        self.login(Rol.FACTURACION)
        self.assertEqual(self.client.get(reverse("indicadores")).status_code, 200)

    def test_admision_solo_ve_sus_cuentas(self):
        propia = self.crear_cuenta()
        ajena = self.crear_cuenta(creador=self.otro_admision)
        self.login(Rol.ADMISION)
        self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[propia.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[ajena.pk])).status_code, 404)
        r = self.client.get(reverse("cuenta_lista"))
        self.assertContains(r, propia.numero)
        self.assertNotContains(r, ajena.numero)
        self.login(Rol.FACTURACION)
        self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[ajena.pk])).status_code, 200)

    def test_salir_exige_post(self):
        self.login(Rol.ADMISION)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("panel")).status_code, 302)


class FlujoVistasTest(BaseTest):
    def test_crear_cuenta(self):
        self.login(Rol.ADMISION)
        r = self.client.post(reverse("cuenta_nueva"), {
            "paciente_documento": "98765", "paciente_nombre": "Ana Prueba", "tipo_servicio": "hospitalizacion",
            "entidad": self.entidad.pk, "fecha_ingreso": "2026-11-01", "valor": "500000",
        })
        cuenta = CuentaMedica.objects.get()
        self.assertRedirects(r, reverse("cuenta_detalle", args=[cuenta.pk]))
        self.assertEqual(cuenta.estado, Estado.ADMITIDA)
        self.assertEqual(cuenta.eventos.count(), 1)
        self.assertEqual(cuenta.atencion.creada_por, self.u[Rol.ADMISION])

    def test_fecha_futura_rechazada(self):
        self.login(Rol.ADMISION)
        r = self.client.post(reverse("cuenta_nueva"), {
            "paciente_documento": "1", "paciente_nombre": "X", "tipo_servicio": "urgencias",
            "entidad": self.entidad.pk, "fecha_ingreso": "2999-01-01", "valor": "1",
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(CuentaMedica.objects.count(), 0)

    def test_flujo_completo_por_http(self):
        cuenta = self.crear_cuenta()
        url_estado = reverse("cuenta_estado", args=[cuenta.pk])
        self.login(Rol.ADMISION)
        self.client.post(url_estado, {"destino": Estado.EN_ATENCION})
        for tipo in (self.hc, self.fac):
            f = SimpleUploadedFile("s.pdf", b"%PDF-1.4 x", content_type="application/pdf")
            self.client.post(reverse("soporte_subir", args=[cuenta.pk]), {"tipo": tipo.pk, "archivo": f})
        self.client.post(url_estado, {"destino": Estado.EGRESADA})
        self.login(Rol.FACTURACION)
        self.client.post(url_estado, {"destino": Estado.EN_VALIDACION})
        self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[cuenta.pk])).status_code, 200)
        self.client.post(reverse("cuenta_validar", args=[cuenta.pk]))
        self.client.post(url_estado, {"destino": Estado.RADICADA})
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.estado, Estado.RADICADA)
        self.login(Rol.AUDITORIA)
        self.client.post(reverse("glosa_nueva", args=[cuenta.pk]), {
            "causal": "tarifas", "valor_glosado": "100000", "descripcion": "Tarifa no pactada"})
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.estado, Estado.RESULTADO)
        glosa = cuenta.glosas.get()
        self.client.post(reverse("glosa_responder", args=[glosa.pk]), {"respuesta": "Contrato adjunto"})
        glosa.refresh_from_db()
        self.assertTrue(glosa.respondida)
        self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[cuenta.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("indicadores")).status_code, 200)

    def test_rol_incorrecto_no_cambia_estado(self):
        cuenta = self.crear_cuenta()
        self.login(Rol.AUDITORIA)
        r = self.client.post(reverse("cuenta_estado", args=[cuenta.pk]), {"destino": Estado.EN_ATENCION}, follow=True)
        cuenta.refresh_from_db()
        self.assertEqual(cuenta.estado, Estado.ADMITIDA)
        self.assertContains(r, "no está autorizado")

    def test_descarga_de_soporte(self):
        cuenta = self.crear_cuenta()
        services.cambiar_estado(cuenta, Estado.EN_ATENCION, self.u[Rol.ADMISION])
        cuenta.refresh_from_db()
        sop = services.cargar_soporte(
            cuenta, self.hc, SimpleUploadedFile("hc.pdf", b"%PDF-1.4 contenido"), self.u[Rol.ADMISION])
        url = reverse("soporte_descargar", args=[sop.pk])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)  # sin sesión no descarga
        self.login(Rol.FACTURACION)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(b"".join(r.streaming_content), b"%PDF-1.4 contenido")
        self.login(Rol.ADMISION)
        self.assertEqual(self.client.get(url).status_code, 200)
        # otra persona de admisión no ve la cuenta ajena
        self.client.logout()
        self.client.login(username="admision2", password="clave-de-prueba")
        self.assertEqual(self.client.get(url).status_code, 404)
