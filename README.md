# Radica — Sistema de trazabilidad digital para la radicación de cuentas médicas

Prototipo funcional (TRL 5) del proyecto de grado **«Sistema de trazabilidad digital para la radicación de cuentas médicas en el área de facturación de Corposalud SAS»**.
Universidad Nacional Abierta y a Distancia (UNAD) · Ingeniería de Sistemas · Curso Proyecto de grado (202016907).

- **Autores:** Oscar Alejandro Benavides Bravo · Jose Luis Portilla Martínez
- **Tutor:** Daniel Andrés Guzmán Arévalo
- **Pila tecnológica:** Python 3.12 · Django 5 · PostgreSQL 16 · arquitectura de tres capas · Scrum (sprints 0–4)

> **Los datos son sintéticos.** Ningún dato real de pacientes ni de Corposalud SAS está en este repositorio (Ley 1581 de 2012). Las tasas de glosa de la demostración imitan el orden de magnitud del diagnóstico, nada más.

## URL de pruebas y credenciales

| | |
|---|---|
| URL pública de pruebas | _https://radica.onrender.com/_ |
| Usuario / rol | `admision` (Admisión) · `facturacion` (Facturación) · `auditoria` (Auditoría) · `admin` (Administrador) |
| Contraseña | La definida en `DEMO_PASSWORD` (por defecto `Radica2026!`, solo para la demostración) |

## Ejecutar con Docker (recomendado)

Requisitos: Docker Desktop (o Docker Engine + Compose).

```bash
git clone <URL-DEL-REPOSITORIO>
cd <carpeta>
docker compose up --build
```

Abra <http://localhost:8000>. En el primer arranque el contenedor genera las migraciones (si faltan), migra la base de datos PostgreSQL, carga los datos de demostración y levanta el servidor.

Las migraciones generadas quedan en `trazabilidad/migrations/`; **súbalas al repositorio** (`git add trazabilidad/migrations && git commit`).

### Pruebas automáticas

```bash
docker compose run --rm -e SEED_DEMO=0 web python manage.py test -v 2
```

Las pruebas usan una base de datos de prueba aislada y cubren servicios, permisos por rol, inmutabilidad de la trazabilidad, indicadores y carga de datos.

### Comandos útiles

```bash
docker compose exec web python manage.py createsuperuser   # otro administrador
docker compose exec web python manage.py seed_demo --reset --cantidad 300   # recargar datos sintéticos
docker compose down -v                                      # apagar y borrar la base de datos local
```

## Ejecutar sin Docker (opcional)

```bash
python -m venv .venv && source .venv/bin/activate      # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations trazabilidad
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

Sin `DATABASE_URL` se usa SQLite local; con ella, PostgreSQL.

## Estructura

```
radica/               configuración del proyecto Django (settings, urls, wsgi)
trazabilidad/         aplicación única
  models.py           8 entidades del diseño (modelo de datos)
  services.py         reglas de negocio: estados, validación documental, plazos, glosas
  indicadores.py      indicadores de gestión
  views.py, forms.py  capa de presentación
  templates/, static/ interfaz responsive (HTML + CSS + JS propio, sin CDN)
  management/commands/seed_demo.py   datos sintéticos reproducibles (semilla 2026)
  tests/              pruebas unitarias, de integración y de aceptación
docker/               script de arranque
docs/                 arquitectura, modelo de datos, historias de usuario, manual, despliegue, Scrum
```

## Qué hace

1. Admisión **registra la atención** y crea la cuenta médica (estado «Admitida»).
2. La cuenta recorre **7 estados**: Admitida → En atención → Egresada → En validación documental → Lista para radicar → Radicada → Glosada o aceptada. Cada cambio exige el rol correspondiente y deja un **evento inmodificable** (quién, cuándo, qué).
3. Se **cargan soportes** (PDF/PNG/JPG, máx. 10 MB). La **validación documental** compara contra los soportes obligatorios parametrizados por entidad y tipo de servicio; si faltan, la cuenta vuelve a «Egresada» y se indica qué falta.
4. **Alertas de plazo**: aviso desde 17 días hábiles de los 22 de radicación y marca de vencida.
5. Registro y respuesta de **glosas** por causal.
6. **Indicadores**: % de glosas por cuentas y por valor, tiempo egreso→radicación, causales, comparación por entidad.
7. **Roles**: Admisión (solo ve las cuentas que creó), Facturación, Auditoría y Administrador (usuarios, parámetros y reglas desde `/admin/`).

## Limitaciones conocidas del prototipo

- Los días hábiles excluyen sábados y domingos, **no** festivos colombianos.
- No hay integración con Salud IPS ni con los portales de las EPS (alcance fuera del prototipo).
- En el plan gratuito de alojamiento los archivos cargados no persisten entre reinicios y el servicio puede «dormir» tras un periodo de inactividad.
- Los soportes de los datos de demostración no tienen archivo adjunto (solo nombre); los cargados durante la prueba sí.

## Control de versiones

Cada integrante hace sus *commits* con su propio usuario de GitHub (`git config user.name` / `user.email`) para que el historial refleje el trabajo colaborativo. Ver `docs/despliegue.md`.
