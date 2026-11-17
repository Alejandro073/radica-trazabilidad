# Historias de usuario y criterios de aceptación

Trazables a los requisitos del documento maestro (RF-01…RF-09, RNF-01…RNF-05). Formato: Dado / Cuando / Entonces.

## HU-01 · Registrar la atención y crear la cuenta (RF-01) — Admisión
Como funcionario de admisión, quiero registrar la atención y crear la cuenta médica para iniciar su seguimiento.
- **CA-1** Dado un usuario con rol Admisión, cuando completa documento, nombre, servicio, entidad, fecha de ingreso y valor, entonces se crea la cuenta en estado «Admitida» con número único y un evento de creación.
- **CA-2** Cuando la fecha de ingreso es futura, entonces el formulario la rechaza y no se crea la cuenta.
- **CA-3** Un usuario de Auditoría no puede abrir el formulario (acceso denegado).
- *Pruebas:* `test_views.FlujoVistasTest.test_crear_cuenta`, `test_fecha_futura_rechazada`, `AccesoTest.test_permisos_por_rol`.

## HU-02 · Ver qué soportes faltan (RF-02, RF-04) — Facturación
Como funcionario de facturación, quiero ver qué soportes faltan para completarlos antes de radicar.
- **CA-1** Dada una entidad y un servicio con reglas, el detalle de la cuenta lista los soportes obligatorios marcando cargado/falta.
- **CA-2** Cuando se ejecuta «Validar documentación» con soportes incompletos, entonces la cuenta vuelve a «Egresada» y el evento indica los soportes faltantes.
- **CA-3** Cuando no hay reglas parametrizadas, entonces la cuenta no supera la validación y se muestra un aviso.
- **CA-4** Cuando los soportes están completos, entonces pasa a «Lista para radicar».
- *Pruebas:* `test_services.FlujoTest.test_validacion_incompleta_devuelve_a_egresada`, `test_sin_reglas_nunca_es_completa`, `test_flujo_completo_deja_trazabilidad`.

## HU-03 · Cargar soportes digitalizados (RF-03) — Facturación / Admisión
Como funcionario de facturación, quiero cargar los soportes digitalizados para tener el expediente completo.
- **CA-1** Se aceptan PDF, PNG y JPG de hasta 10 MB; otros formatos o tamaños se rechazan con mensaje.
- **CA-2** Cada carga genera un evento de trazabilidad.
- **CA-3** En cuentas radicadas ya no se pueden cargar soportes.
- **CA-4** El archivo solo se descarga con sesión iniciada y dentro del alcance del rol.
- *Pruebas:* `test_formato_de_soporte_invalido`, `test_tamano_de_soporte_excedido`, `test_no_se_carga_soporte_en_cuenta_radicada`, `test_descarga_de_soporte`.

## HU-04 · Consultar el historial (RF-05, RF-06) — Usuario autorizado
Como usuario autorizado, quiero consultar el historial de una cuenta para saber en qué etapa está y quién la tuvo.
- **CA-1** El detalle muestra el estado actual en un indicador de 7 pasos y una línea de tiempo con fecha, usuario y detalle de cada evento.
- **CA-2** Cada transición exige el rol correcto y la secuencia válida; si no, se rechaza con mensaje y no cambia el estado.
- **CA-3** Los eventos no se pueden modificar ni eliminar (RNF-02).
- **CA-4** Aparece alerta cuando transcurren ≥ 17 días hábiles desde el egreso y «vencida» después de 22.
- *Pruebas:* `test_rol_no_autorizado`, `test_no_se_permiten_saltos`, `InmutabilidadTest`, `PlazosTest`.

## HU-05 · Registrar glosas (RF-07) — Auditoría / Facturación
Como auditor de cuentas, quiero registrar las glosas con su causal y respuesta para conocer sus causas más frecuentes.
- **CA-1** Solo se registran glosas en cuentas radicadas; la cuenta pasa a «Glosada o aceptada» con resultado «Glosada».
- **CA-2** Cada glosa guarda causal, valor y descripción; luego puede responderse una sola vez.
- **CA-3** Una cuenta aceptada no admite glosas.
- *Pruebas:* `test_glosa_solo_en_cuenta_radicada`, `test_responder_glosa`, `test_aceptar_cuenta`.

## HU-06 · Ver indicadores (RF-08) — Jefe de facturación
Como jefe de facturación, quiero ver indicadores de glosas y tiempos para tomar decisiones.
- **CA-1** Se muestran % de cuentas glosadas, % del valor glosado, tiempo promedio egreso→radicación y % radicadas dentro del plazo.
- **CA-2** Se muestran causales de glosa y comparación por entidad.
- **CA-3** Con base de datos vacía, los indicadores muestran ceros sin errores.
- **CA-4** Admisión no accede a indicadores.
- *Pruebas:* `test_indicadores.*`, `AccesoTest.test_permisos_por_rol`.

## HU-07 · Asignar roles (RF-09) — Administrador
Como administrador, quiero asignar roles a los usuarios para que cada uno acceda solo a sus funciones.
- **CA-1** Desde `/admin/` el administrador crea usuarios y edita el rol del perfil.
- **CA-2** Admisión solo ve las cuentas que creó; Facturación, Auditoría y Administrador ven todas.
- **CA-3** Sin sesión, toda pantalla (excepto `/salud/`) redirige al ingreso.
- *Pruebas:* `AccesoTest.*`.

## Trazabilidad de requisitos no funcionales
| RNF | Verificación en el prototipo |
|---|---|
| RNF-01 Seguridad | Roles + `login_required`; HTTPS y cookies seguras en el despliegue (`SECURE_COOKIES=1`) |
| RNF-02 Integridad | `InmutabilidadTest` |
| RNF-03 Privacidad | Datos 100 % sintéticos (`seed_demo`) |
| RNF-04 Usabilidad | Revisión con el personal de facturación en cada sprint (ver actas) |
| RNF-05 Desempeño | Medir con `seed_demo --cantidad 6000`; registrar el tiempo de la consulta de trazabilidad (meta < 3 s) en el informe de pruebas |
