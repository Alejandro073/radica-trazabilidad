# Despliegue y publicación

## A. Repositorio público en GitHub (cada integrante con su usuario)

```bash
cd radica
git init -b main
git config user.name "Su nombre"          # cada integrante usa su propio usuario en su equipo
git config user.email "su-correo@ejemplo.com"
git add .
git commit -m "Prototipo inicial del sistema de trazabilidad"
git remote add origin https://github.com/<usuario>/<repositorio>.git
git push -u origin main
```

Para que el historial muestre trabajo de ambos: el segundo integrante clona el repositorio, trabaja en una rama (`git switch -c sprint-3`), hace *commits* con su usuario y abre un *pull request* que el primero revisa. Agregue al tutor como colaborador (Settings → Collaborators) o, al ser público, solo comparta el enlace en el anexo.

Antes del primer `git push`, ejecute el prototipo con Docker, suba la carpeta `trazabilidad/migrations/` generada y verifique que **no** haya `.env` ni contraseñas reales.

## B. URL pública de pruebas en Render

1. Cree cuenta en <https://render.com> y conecte su GitHub.
2. **New → Blueprint** → seleccione el repositorio. Render lee `render.yaml` y crea la base PostgreSQL y el servicio Docker.
3. Cuando lo pida, escriba `DEMO_PASSWORD` (contraseña de los usuarios de demostración).
4. Espere el primer despliegue; la URL queda como `https://radica-xxxx.onrender.com`.
5. Abra `/salud/` (debe responder `{"status": "ok"}`) y luego inicie sesión.

**Límites del plan gratuito (verifique los vigentes en render.com antes de la sustentación):** el servicio puede suspenderse tras inactividad y tardar en despertar; la base de datos gratuita puede tener caducidad; los archivos cargados no persisten entre reinicios. Abra la URL unos minutos antes del video y de la sustentación.

Alternativa: Railway u otro servicio con soporte Docker; solo se necesitan las variables `DATABASE_URL`, `SECRET_KEY`, `SECURE_COOKIES=1`, `SSL_REDIRECT=0`, `SEED_DEMO=1` y `DEMO_PASSWORD`.

## C. Variables de entorno

| Variable | Uso |
|---|---|
| `SECRET_KEY` | Clave de Django (generada por Render) |
| `DEBUG` | `0` en producción |
| `DATABASE_URL` | Cadena de conexión PostgreSQL |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | Se completan solas con `RENDER_EXTERNAL_HOSTNAME` |
| `SEED_DEMO` | `1` carga datos sintéticos si la base está vacía |
| `DEMO_PASSWORD` | Contraseña de los usuarios de demostración |
| `SECURE_COOKIES`, `SSL_REDIRECT` | Cookies seguras / redirección a HTTPS |
