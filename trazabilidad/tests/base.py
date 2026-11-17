import shutil
import tempfile
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from trazabilidad.models import (
    Atencion,
    CuentaMedica,
    EntidadPagadora,
    ReglaSoporte,
    Rol,
    TipoServicio,
    TipoSoporte,
)


class BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.u = {}
        for rol in Rol.values:
            user = User.objects.create_user(username=rol, password="clave-de-prueba")
            user.perfil.rol = rol
            user.perfil.save()
            cls.u[rol] = user
        cls.otro_admision = User.objects.create_user(username="admision2", password="clave-de-prueba")
        cls.entidad = EntidadPagadora.objects.create(nombre="EPS Prueba", plazo_radicacion_dias=22)
        cls.hc = TipoSoporte.objects.create(nombre="Historia clínica")
        cls.fac = TipoSoporte.objects.create(nombre="Factura de venta")
        for t in (cls.hc, cls.fac):
            ReglaSoporte.objects.create(
                entidad=cls.entidad, tipo_servicio=TipoServicio.HOSPITALIZACION, tipo_soporte=t
            )

    def setUp(self):
        # Los archivos de prueba van a una carpeta temporal, no al proyecto.
        media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media, ignore_errors=True)
        ov = override_settings(MEDIA_ROOT=media)
        ov.enable()
        self.addCleanup(ov.disable)

    def crear_cuenta(self, creador=None, servicio=TipoServicio.HOSPITALIZACION, valor=1_000_000,
                     ingreso=date(2026, 10, 1), entidad=None):
        atencion = Atencion.objects.create(
            paciente_documento="123456", paciente_nombre="Paciente de Prueba",
            tipo_servicio=servicio, entidad=entidad or self.entidad, fecha_ingreso=ingreso,
            creada_por=creador or self.u[Rol.ADMISION],
        )
        return CuentaMedica.objects.create(atencion=atencion, valor=valor)

    def login(self, rol):
        self.client.login(username=rol, password="clave-de-prueba")
