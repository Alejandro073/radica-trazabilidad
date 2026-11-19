# Informe de pruebas — Prototipo Radica (TRL 5)

## 1\. Entorno

|Elemento|Valor|
|-|-|
|Entorno local|Docker Desktop en Windows; contenedores Python 3.12 (Django 5) y PostgreSQL 16|
|Entorno de despliegue|Render (servicio Docker y PostgreSQL gratuito): https://radica.onrender.com/|
|Repositorio|https://github.com/Alejandro073/radica-trazabilidad|
|Fecha de ejecución|17 de noviembre de 2026|
|Ejecutó|Oscar Alejandro Benavides Bravo|
|Datos|Sintéticos (`seed\_demo`, semilla 2026); no hay datos reales de pacientes|

## 2\. Pruebas automáticas

Comando: `docker compose run --rm web python manage.py test -v 2`

|Módulo|Pruebas|Qué verifica|
|-|-|-|
|`test\_services`|19|Flujo de estados, roles, validación documental, soportes, glosas, plazos en días hábiles e inmodificabilidad de los eventos|
|`test\_views`|12|Acceso por sesión y rol, alcance de Admisión, flujo completo por HTTP, descarga protegida de soportes|
|`test\_indicadores`|3|Porcentajes de glosa, tiempo promedio de radicación y caso sin datos|
|`test\_seed`|5|Carga de datos demo coherente y reproducible; todas las pantallas se muestran sin error|
|**Total**|**39**||

**Resultado:** `Ran 39 tests in 13.528s — OK`. La base de datos de prueba se creó y se destruyó automáticamente (`test\_radica`).
*(Figura: captura de la consola con este resultado.)*

## 3\. Pruebas de aceptación manuales (en la URL de pruebas)

Marcar «Cumple» según lo observado y referenciar la captura.

|ID|Historia / RNF|Pasos|Resultado esperado|Captura|¿Cumple?|
|-|-|-|-|-|-|
|PA-01|HU-01|Admisión crea una cuenta|Estado «Admitida» y evento de creación|PA-01.png|SI|
|PA-02|HU-03|Cargar un PDF y un archivo no permitido|PDF aceptado; archivo no permitido rechazado|PA-02.png|SI|
|PA-03|HU-02|Validar con soportes incompletos|Vuelve a «Egresada» e indica qué falta||NO|
|PA-04|HU-02|Validar con soportes completos|«Lista para radicar»|PA-04.png|SI|
|PA-05|HU-04|Radicar y abrir la línea de tiempo|Evento de radicación con usuario y hora|PA-05.png|SI|
|PA-06|HU-05|Registrar y responder una glosa|Estado «Glosada o aceptada»|PA-06.png|SI|
|PA-07|HU-06|Abrir Indicadores como Facturación|Indicadores coherentes con los datos|PA-07.png|SI|
|PA-08|HU-07 / RNF-01|Abrir Indicadores como Admisión|Acceso denegado||NO|
|PA-09|RNF-02|Intentar editar o borrar un evento desde la administración|No existe la opción||NO|

## 4\. Rendimiento (RNF-05)

**Meta:** abrir la lista de cuentas y el detalle de una cuenta en menos de 3 segundos con un volumen alto de datos.

**Condiciones:** entorno local (Docker Compose, PostgreSQL), 6.000 cuentas sintéticas (`docker compose exec web python manage.py seed\_demo --reset --cantidad 6000`), usuario `facturacion`, medición con la pestaña Red (Network) del navegador, 3 repeticiones por página. Fecha: 19/11/2026.

|Página|Medición|Respuesta del servidor (documento HTML)|Tiempo total de carga («Finalizado»)|
|-|-|-|-|
|Lista de cuentas (`/cuentas/`)|1|54 ms|377 ms|
||2|41 ms|365 ms|
||3|36 ms|283 ms|
||**Promedio**|**43,7 ms**|**341,7 ms**|
|Detalle de cuenta (`/cuentas/12166/`)|1|32 ms|443 ms|
||2|32 ms|255 ms|
||3|24 ms|196 ms|
||**Promedio**|**29,3 ms**|**298 ms**|

**Resultado: Cumple.** Ambas páginas cargan por completo en menos de 0,5 s, muy por debajo de la meta de 3 s. La medición se hizo en entorno local; en el plan gratuito de Render los tiempos pueden ser mayores (ver limitaciones). Figuras: capturas de la pestaña Red de cada medición.

## 5\. Pruebas de interfaz responsive

Revisión visual en escritorio (captura de Indicadores) y en pantalla angosta o celular.

|Ancho|Resultado|Captura|
|-|-|-|
|Escritorio (1280 px)|Cumple: menú, tablas e indicadores se ven completos|responsive\_escritorio\_indicadores.png|
|Celular|Cumple: el menú se colapsa en un botón «Menú», las alertas del Panel se muestran en tarjetas de ancho completo y no hay desplazamiento horizontal. Observación: bajo contraste de los enlaces del menú desplegado.|responsive\_celular\_panel.png|

## 6\. Limitaciones y defectos

|#|Descripción|Estado|
|-|-|-|
|1|Los días hábiles no descuentan festivos colombianos|Limitación conocida del prototipo|
|2|Las barras de causales de glosa quedaban desalineadas|Corregido (`app.css`)|
|3|En el plan gratuito de Render el servicio puede tardar en despertar y los archivos cargados no persisten entre reinicios|Limitación del alojamiento|
|4|Aún no hay validación de usabilidad con el personal de Corposalud (RNF-04)|Pendiente|

## 7\. Conclusión

Las 39 pruebas automáticas pasaron y el prototipo funciona en el entorno local y en la URL pública de pruebas. El desempeño con 6.000 cuentas cumple la meta (RNF-05). Queda pendiente la validación de usabilidad con el personal de facturación.

