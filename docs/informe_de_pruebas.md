# Informe de pruebas (entorno relevante: despliegue en Render + Docker local)

> Complete con los resultados **reales** de cada ejecución. Esta plantilla solo fija qué se prueba.

## 1. Entorno
| Elemento | Valor |
|---|---|
| URL de pruebas | |
| Fecha y hora de la ejecución | |
| Versión (hash del *commit*) | |
| Ejecutó | |

## 2. Pruebas automáticas (`python manage.py test -v 2`)
| Módulo | Pruebas | Resultado |
|---|---|---|
| test_services | | |
| test_views | | |
| test_indicadores | | |
| test_seed | | |
Total: ___ pruebas, ___ correctas, ___ fallidas. Pegue aquí la salida de la consola.

## 3. Pruebas de aceptación manuales en la URL de pruebas
| ID | Historia | Pasos | Resultado esperado | Resultado obtenido | ¿Cumple? |
|---|---|---|---|---|---|
| PA-01 | HU-01 | Admisión crea cuenta | Estado «Admitida» + evento | | |
| PA-02 | HU-03 | Cargar PDF y un .exe | PDF aceptado; .exe rechazado | | |
| PA-03 | HU-02 | Validar con soportes incompletos | Vuelve a «Egresada» y lista faltantes | | |
| PA-04 | HU-02 | Validar con soportes completos | «Lista para radicar» | | |
| PA-05 | HU-04 | Radicar y ver línea de tiempo | Evento de radicación con usuario y hora | | |
| PA-06 | HU-05 | Registrar y responder glosa | Estado «Glosada o aceptada» | | |
| PA-07 | HU-06 | Abrir indicadores como Facturación | KPI coherentes con los datos | | |
| PA-08 | HU-07 | Abrir indicadores como Admisión | Acceso denegado | | |
| PA-09 | RNF-02 | Intentar editar/borrar un evento (admin) | No hay opción de editar ni borrar | | |

## 4. Rendimiento (RNF-05)
Cargar 6.000 cuentas (`seed_demo --reset --cantidad 6000`) y medir la carga del detalle de una cuenta con historial. Meta: < 3 s.
| Medición | Tiempo | ¿Cumple? |
|---|---|---|
| | | |

## 5. Responsive
Revisión en celular (≈ 390 px), tableta (≈ 768 px) y escritorio (≥ 1280 px): navegación, tablas y formularios.

## 6. Defectos encontrados y correcciones
| # | Descripción | Gravedad | Estado |
|---|---|---|---|
| | | | |

## 7. Conclusión
