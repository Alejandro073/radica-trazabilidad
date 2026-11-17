"""Modelo de datos del prototipo (8 entidades del diseño integral).

Usuario (django.contrib.auth + Perfil), Atención, Cuenta médica, Entidad
responsable de pago, Tipo de soporte, Soporte cargado, Evento de trazabilidad
y Glosa.
"""
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    ADMISION = "admision", "Admisión"
    FACTURACION = "facturacion", "Facturación"
    AUDITORIA = "auditoria", "Auditoría"
    ADMINISTRADOR = "administrador", "Administrador"


class Perfil(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="perfil")
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.ADMISION)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfiles"

    def __str__(self):
        return f"{self.user} · {self.get_rol_display()}"


class EntidadPagadora(models.Model):
    """Entidad responsable de pago (EPS, aseguradora, etc.)."""

    nombre = models.CharField(max_length=120, unique=True)
    nit = models.CharField(max_length=20, blank=True)
    plazo_radicacion_dias = models.PositiveSmallIntegerField(
        default=22, help_text="Plazo de radicación en días hábiles contados desde el egreso."
    )
    activa = models.BooleanField(default=True)

    class Meta:
        verbose_name = "entidad responsable de pago"
        verbose_name_plural = "entidades responsables de pago"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoSoporte(models.Model):
    nombre = models.CharField(max_length=120, unique=True)
    descripcion = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "tipo de soporte"
        verbose_name_plural = "tipos de soporte"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class TipoServicio(models.TextChoices):
    HOSPITALIZACION = "hospitalizacion", "Hospitalización"
    URGENCIAS = "urgencias", "Urgencias"
    QUIROFANO = "quirofano", "Quirófano"
    CONSULTA = "consulta", "Consulta externa"
    APOYO = "apoyo", "Apoyo diagnóstico"


class ReglaSoporte(models.Model):
    """Soportes obligatorios por entidad y tipo de servicio (parametrizable)."""

    entidad = models.ForeignKey(EntidadPagadora, on_delete=models.CASCADE, related_name="reglas")
    tipo_servicio = models.CharField(max_length=20, choices=TipoServicio.choices)
    tipo_soporte = models.ForeignKey(TipoSoporte, on_delete=models.CASCADE, related_name="reglas")

    class Meta:
        verbose_name = "regla de soporte obligatorio"
        verbose_name_plural = "reglas de soportes obligatorios"
        constraints = [
            models.UniqueConstraint(
                fields=["entidad", "tipo_servicio", "tipo_soporte"], name="regla_soporte_unica"
            )
        ]
        ordering = ["entidad", "tipo_servicio", "tipo_soporte"]

    def __str__(self):
        return f"{self.entidad} · {self.get_tipo_servicio_display()} · {self.tipo_soporte}"


class Atencion(models.Model):
    paciente_documento = models.CharField("documento del paciente", max_length=20)
    paciente_nombre = models.CharField("nombre del paciente", max_length=150)
    tipo_servicio = models.CharField(max_length=20, choices=TipoServicio.choices)
    entidad = models.ForeignKey(EntidadPagadora, on_delete=models.PROTECT, related_name="atenciones")
    fecha_ingreso = models.DateField()
    fecha_egreso = models.DateField(null=True, blank=True)
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="atenciones"
    )

    class Meta:
        verbose_name = "atención"
        verbose_name_plural = "atenciones"
        ordering = ["-fecha_ingreso"]

    def __str__(self):
        return f"{self.paciente_nombre} ({self.paciente_documento})"


class Estado(models.TextChoices):
    ADMITIDA = "admitida", "Admitida"
    EN_ATENCION = "en_atencion", "En atención"
    EGRESADA = "egresada", "Egresada"
    EN_VALIDACION = "en_validacion", "En validación documental"
    LISTA = "lista", "Lista para radicar"
    RADICADA = "radicada", "Radicada"
    RESULTADO = "resultado", "Glosada o aceptada"


ORDEN_ESTADOS = [e for e, _ in Estado.choices]


class Resultado(models.TextChoices):
    PENDIENTE = "", "Pendiente"
    GLOSADA = "glosada", "Glosada"
    ACEPTADA = "aceptada", "Aceptada"


class CuentaMedica(models.Model):
    numero = models.CharField(max_length=20, unique=True, editable=False)
    atencion = models.OneToOneField(Atencion, on_delete=models.PROTECT, related_name="cuenta")
    valor = models.DecimalField("valor facturado (COP)", max_digits=14, decimal_places=0, default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ADMITIDA, db_index=True)
    resultado = models.CharField(max_length=10, choices=Resultado.choices, blank=True, default="")
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_radicacion = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "cuenta médica"
        verbose_name_plural = "cuentas médicas"
        ordering = ["-fecha_creacion", "-id"]

    def __str__(self):
        return self.numero

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = f"CM-{timezone.localdate().year}-{uuid.uuid4().hex[:6].upper()}"
        super().save(*args, **kwargs)

    @property
    def entidad(self):
        return self.atencion.entidad

    @property
    def indice_estado(self):
        return ORDEN_ESTADOS.index(self.estado)


class SoporteCargado(models.Model):
    cuenta = models.ForeignKey(CuentaMedica, on_delete=models.CASCADE, related_name="soportes")
    tipo = models.ForeignKey(TipoSoporte, on_delete=models.PROTECT, related_name="cargas")
    archivo = models.FileField(upload_to="soportes/%Y/%m/", blank=True)
    nombre_archivo = models.CharField(max_length=255)
    cargado_por = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    fecha = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "soporte cargado"
        verbose_name_plural = "soportes cargados"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.tipo} · {self.cuenta}"


class EventoQuerySet(models.QuerySet):
    def update(self, *args, **kwargs):
        raise PermissionDenied("Los eventos de trazabilidad son inmodificables.")

    def delete(self):
        raise PermissionDenied("Los eventos de trazabilidad no se pueden eliminar.")


class TipoEvento(models.TextChoices):
    CREACION = "creacion", "Creación"
    ESTADO = "estado", "Cambio de estado"
    SOPORTE = "soporte", "Soporte cargado"
    VALIDACION = "validacion", "Validación documental"
    RADICACION = "radicacion", "Radicación"
    GLOSA = "glosa", "Glosa"
    RESPUESTA = "respuesta", "Respuesta de glosa"


class EventoTrazabilidad(models.Model):
    """Registro inmodificable: quién, cuándo y qué ocurrió con una cuenta."""

    cuenta = models.ForeignKey(CuentaMedica, on_delete=models.PROTECT, related_name="eventos")
    fecha = models.DateTimeField(default=timezone.now, editable=False)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    tipo = models.CharField(max_length=20, choices=TipoEvento.choices)
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_nuevo = models.CharField(max_length=20, blank=True)
    detalle = models.CharField(max_length=500, blank=True)

    objects = EventoQuerySet.as_manager()

    class Meta:
        verbose_name = "evento de trazabilidad"
        verbose_name_plural = "eventos de trazabilidad"
        ordering = ["fecha", "id"]

    def __str__(self):
        return f"{self.cuenta} · {self.get_tipo_display()} · {self.fecha:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise PermissionDenied("Los eventos de trazabilidad son inmodificables.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("Los eventos de trazabilidad no se pueden eliminar.")


class CausalGlosa(models.TextChoices):
    SOPORTES = "soportes", "Soportes"
    TARIFAS = "tarifas", "Tarifas"
    AUTORIZACIONES = "autorizaciones", "Autorizaciones"
    FACTURACION = "facturacion", "Facturación"
    DERECHOS = "derechos", "Derechos del paciente"
    OTRA = "otra", "Otra"


class Glosa(models.Model):
    cuenta = models.ForeignKey(CuentaMedica, on_delete=models.CASCADE, related_name="glosas")
    causal = models.CharField(max_length=20, choices=CausalGlosa.choices)
    valor_glosado = models.DecimalField(max_digits=14, decimal_places=0, default=0)
    descripcion = models.CharField(max_length=500, blank=True)
    fecha = models.DateField(default=timezone.localdate)
    respondida = models.BooleanField(default=False)
    respuesta = models.CharField(max_length=500, blank=True)
    fecha_respuesta = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "glosa"
        verbose_name_plural = "glosas"
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.cuenta} · {self.get_causal_display()}"
