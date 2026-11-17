from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Q
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import indicadores, services
from .forms import CuentaForm, GlosaForm, RespuestaGlosaForm, SoporteForm
from .models import (
    Atencion,
    CuentaMedica,
    EntidadPagadora,
    Estado,
    Glosa,
    ORDEN_ESTADOS,
    Resultado,
    Rol,
    SoporteCargado,
    TipoEvento,
)
from .permisos import rol_de, rol_requerido

TODOS = (Rol.ADMISION, Rol.FACTURACION, Rol.AUDITORIA, Rol.ADMINISTRADOR)
GESTION = (Rol.FACTURACION, Rol.AUDITORIA, Rol.ADMINISTRADOR)

ETIQUETA_ACCION = {
    Estado.EN_ATENCION.value: "Iniciar atención",
    Estado.EGRESADA.value: "Registrar egreso",
    Estado.EN_VALIDACION.value: "Enviar a validación documental",
    Estado.RADICADA.value: "Radicar ante la entidad",
}


def cuentas_visibles(user):
    """Admisión solo ve las cuentas que creó; los demás roles ven todas (RF-08)."""
    qs = CuentaMedica.objects.select_related("atencion", "atencion__entidad")
    if rol_de(user) == Rol.ADMISION:
        qs = qs.filter(atencion__creada_por=user)
    return qs


def _cuenta_o_404(request, pk):
    return get_object_or_404(cuentas_visibles(request.user), pk=pk)


def salud(request):
    """Punto de comprobación para el alojamiento (sin autenticación)."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        return JsonResponse({"status": "ok"})
    except Exception:  # pragma: no cover
        return JsonResponse({"status": "error"}, status=503)


@rol_requerido(*TODOS)
def panel(request):
    cuentas = cuentas_visibles(request.user)
    conteo = {valor: 0 for valor in ORDEN_ESTADOS}
    for c in cuentas.values_list("estado", flat=True):
        conteo[c] += 1
    estados = [(valor, etiqueta, conteo[valor]) for valor, etiqueta in Estado.choices]

    pendientes = cuentas.filter(
        estado__in=(Estado.EGRESADA, Estado.EN_VALIDACION, Estado.LISTA),
        atencion__fecha_egreso__isnull=False,
    )
    alertas = []
    for c in pendientes:
        nivel = services.alerta_plazo(c)
        if nivel:
            alertas.append({"cuenta": c, "nivel": nivel, "restantes": services.dias_restantes(c)})
    alertas.sort(key=lambda a: (a["nivel"] != "vencida", a["restantes"]))

    return render(request, "trazabilidad/panel.html", {
        "estados": estados,
        "total": sum(conteo.values()),
        "alertas": alertas[:10],
        "n_alertas": len(alertas),
        "recientes": cuentas.order_by("-fecha_creacion", "-id")[:6],
    })


@rol_requerido(*TODOS)
def cuenta_lista(request):
    qs = cuentas_visibles(request.user)
    q = request.GET.get("q", "").strip()
    estado = request.GET.get("estado", "")
    entidad = request.GET.get("entidad", "")
    if q:
        qs = qs.filter(
            Q(numero__icontains=q)
            | Q(atencion__paciente_documento__icontains=q)
            | Q(atencion__paciente_nombre__icontains=q)
        )
    if estado in ORDEN_ESTADOS:
        qs = qs.filter(estado=estado)
    if entidad.isdigit():
        qs = qs.filter(atencion__entidad_id=int(entidad))
    pagina = Paginator(qs.order_by("-fecha_creacion", "-id"), 15).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "trazabilidad/cuenta_lista.html", {
        "pagina": pagina,
        "q": q,
        "estado": estado,
        "entidad": entidad,
        "estados": Estado.choices,
        "entidades": EntidadPagadora.objects.filter(activa=True),
        "querystring": params.urlencode(),
    })


@rol_requerido(Rol.ADMISION, Rol.ADMINISTRADOR)
def cuenta_nueva(request):
    form = CuentaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            atencion = Atencion.objects.create(
                paciente_documento=d["paciente_documento"],
                paciente_nombre=d["paciente_nombre"],
                tipo_servicio=d["tipo_servicio"],
                entidad=d["entidad"],
                fecha_ingreso=d["fecha_ingreso"],
                creada_por=request.user,
            )
            cuenta = CuentaMedica.objects.create(atencion=atencion, valor=d["valor"])
            services.registrar_evento(
                cuenta, request.user, TipoEvento.CREACION, "Cuenta médica creada en admisión.",
                "", Estado.ADMITIDA,
            )
        messages.success(request, f"Cuenta {cuenta.numero} creada.")
        return redirect("cuenta_detalle", pk=cuenta.pk)
    return render(request, "trazabilidad/cuenta_form.html", {"form": form})


def _pasos(cuenta):
    pasos = []
    for i, (valor, etiqueta) in enumerate(Estado.choices):
        if i < cuenta.indice_estado:
            clase = "hecho"
        elif i == cuenta.indice_estado:
            clase = "actual"
        else:
            clase = "pendiente"
        pasos.append({"etiqueta": etiqueta, "clase": clase, "n": i + 1})
    return pasos


@rol_requerido(*TODOS)
def cuenta_detalle(request, pk):
    cuenta = _cuenta_o_404(request, pk)
    rol = rol_de(request.user)
    destinos = services.acciones_disponibles(cuenta, request.user)
    en_validacion = cuenta.estado == Estado.EN_VALIDACION
    acciones = [] if en_validacion else [
        {"destino": d, "etiqueta": ETIQUETA_ACCION[d]} for d in destinos if d in ETIQUETA_ACCION
    ]
    glosa_ok = (
        cuenta.estado in (Estado.RADICADA, Estado.RESULTADO)
        and rol in GESTION
        and not (cuenta.estado == Estado.RESULTADO and cuenta.resultado == Resultado.ACEPTADA)
    )
    nivel = services.alerta_plazo(cuenta)
    return render(request, "trazabilidad/cuenta_detalle.html", {
        "cuenta": cuenta,
        "pasos": _pasos(cuenta),
        "soportes_estado": services.estado_soportes(cuenta),
        "soportes": cuenta.soportes.select_related("tipo", "cargado_por"),
        "eventos": cuenta.eventos.select_related("usuario"),
        "glosas": cuenta.glosas.all(),
        "acciones": acciones,
        "puede_validar": en_validacion and bool(destinos),
        "puede_aceptar": cuenta.estado == Estado.RADICADA and Estado.RESULTADO in destinos,
        "puede_glosar": glosa_ok,
        "puede_responder": rol in GESTION,
        "puede_cargar": cuenta.estado in services.ESTADOS_CARGA
        and rol in (Rol.ADMISION, Rol.FACTURACION, Rol.ADMINISTRADOR),
        "form_soporte": SoporteForm(),
        "form_glosa": GlosaForm(),
        "form_respuesta": RespuestaGlosaForm(),
        "alerta": nivel,
        "restantes": services.dias_restantes(cuenta),
    })


def _ejecutar(request, pk, funcion, ok_msg):
    cuenta = _cuenta_o_404(request, pk)
    try:
        resultado = funcion(cuenta)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
        return None
    messages.success(request, ok_msg)
    return resultado


@require_POST
@rol_requerido(*TODOS)
def cuenta_estado(request, pk):
    destino = request.POST.get("destino", "")
    if destino not in ORDEN_ESTADOS:
        raise Http404
    _ejecutar(
        request, pk,
        lambda c: services.cambiar_estado(c, destino, request.user),
        f"Estado actualizado a «{Estado(destino).label}».",
    )
    return redirect("cuenta_detalle", pk=pk)


@require_POST
@rol_requerido(*TODOS)
def cuenta_validar(request, pk):
    cuenta = _cuenta_o_404(request, pk)
    try:
        _, ok, detalle = services.validar_documental(cuenta, request.user)
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    else:
        (messages.success if ok else messages.warning)(request, detalle)
    return redirect("cuenta_detalle", pk=pk)


@require_POST
@rol_requerido(*TODOS)
def cuenta_aceptar(request, pk):
    _ejecutar(request, pk, lambda c: services.aceptar_cuenta(c, request.user), "Cuenta aceptada por la entidad.")
    return redirect("cuenta_detalle", pk=pk)


@require_POST
@rol_requerido(*TODOS)
def soporte_subir(request, pk):
    cuenta = _cuenta_o_404(request, pk)
    form = SoporteForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Seleccione el tipo de soporte y un archivo.")
    else:
        try:
            services.cargar_soporte(cuenta, form.cleaned_data["tipo"], form.cleaned_data["archivo"], request.user)
            messages.success(request, "Soporte cargado.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return redirect("cuenta_detalle", pk=pk)


@rol_requerido(*TODOS)
def soporte_descargar(request, pk):
    soporte = get_object_or_404(SoporteCargado, pk=pk)
    _cuenta_o_404(request, soporte.cuenta_id)  # respeta el alcance por rol
    if not soporte.archivo:
        raise Http404("Este soporte de demostración no tiene archivo adjunto.")
    try:
        return FileResponse(soporte.archivo.open("rb"), as_attachment=True, filename=soporte.nombre_archivo)
    except FileNotFoundError:
        raise Http404("Archivo no disponible.")


@require_POST
@rol_requerido(*GESTION)
def glosa_nueva(request, pk):
    cuenta = _cuenta_o_404(request, pk)
    form = GlosaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revise los datos de la glosa.")
    else:
        d = form.cleaned_data
        try:
            services.agregar_glosa(cuenta, d["causal"], d["valor_glosado"], d["descripcion"], request.user)
            messages.success(request, "Glosa registrada.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return redirect("cuenta_detalle", pk=pk)


@require_POST
@rol_requerido(*GESTION)
def glosa_responder(request, pk):
    glosa = get_object_or_404(Glosa, pk=pk)
    _cuenta_o_404(request, glosa.cuenta_id)
    form = RespuestaGlosaForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Escriba la respuesta a la glosa.")
    else:
        try:
            services.responder_glosa(glosa, form.cleaned_data["respuesta"], request.user)
            messages.success(request, "Respuesta registrada.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    return redirect("cuenta_detalle", pk=glosa.cuenta_id)


@rol_requerido(*GESTION)
def indicadores_vista(request):
    datos = indicadores.todos()
    maximo = max([c["n"] for c in datos["causas"]], default=1)
    for c in datos["causas"]:
        c["ancho"] = round(c["n"] * 100 / maximo)
    return render(request, "trazabilidad/indicadores.html", {"d": datos, "hoy": timezone.localdate()})
