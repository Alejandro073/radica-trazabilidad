from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from trazabilidad import indicadores
from trazabilidad.models import CuentaMedica, EventoTrazabilidad


class SeedTest(TestCase):
    def cargar(self, *args, **kw):
        call_command("seed_demo", *args, stdout=StringIO(), **kw)

    def test_carga_y_es_coherente(self):
        self.cargar(cantidad=40)
        self.assertEqual(CuentaMedica.objects.count(), 40)
        self.assertEqual(get_user_model().objects.filter(username__in=["admin", "admision", "facturacion", "auditoria"]).count(), 4)
        for c in CuentaMedica.objects.all():
            ultimo = c.eventos.last()
            self.assertEqual(ultimo.estado_nuevo, c.estado, c.numero)

    def test_idempotente_con_solo_si_vacio(self):
        self.cargar(cantidad=10)
        self.cargar(cantidad=10, solo_si_vacio=True)
        self.assertEqual(CuentaMedica.objects.count(), 10)

    def test_reset(self):
        self.cargar(cantidad=10)
        self.cargar(cantidad=5, reset=True)
        self.assertEqual(CuentaMedica.objects.count(), 5)
        self.assertEqual(EventoTrazabilidad.objects.filter(cuenta__isnull=False).count(), EventoTrazabilidad.objects.count())

    def test_misma_semilla_mismos_datos(self):
        self.cargar(cantidad=15)
        a = list(CuentaMedica.objects.order_by("numero").values_list("numero", "estado", "valor"))
        self.cargar(cantidad=15, reset=True)
        b = list(CuentaMedica.objects.order_by("numero").values_list("numero", "estado", "valor"))
        self.assertEqual(a, b)

    def test_todas_las_pantallas_renderizan(self):
        self.cargar(cantidad=60)
        self.client.login(username="admin", password="Radica2026!")
        for url in ("panel", "cuenta_lista", "indicadores", "cuenta_nueva"):
            self.assertEqual(self.client.get(reverse(url)).status_code, 200, url)
        for c in CuentaMedica.objects.all():
            self.assertEqual(self.client.get(reverse("cuenta_detalle", args=[c.pk])).status_code, 200, c.numero)
        self.assertEqual(self.client.get(reverse("cuenta_lista") + "?q=CM-&estado=radicada&entidad=1").status_code, 200)
        self.assertGreater(indicadores.resumen_glosas()["radicadas"], 0)
