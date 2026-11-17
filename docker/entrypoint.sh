#!/bin/sh
# Arranque: migraciones, estáticos, datos de demostración (opcional) y gunicorn.
set -e

# Si el repositorio aún no trae migraciones, se generan (y quedan en el volumen).
if [ -z "$(ls trazabilidad/migrations/0*.py 2>/dev/null)" ]; then
  echo "[radica] Generando migraciones iniciales..."
  python manage.py makemigrations trazabilidad --noinput
fi

# La base de datos puede tardar unos segundos en aceptar conexiones.
intentos=0
until python manage.py migrate --noinput; do
  intentos=$((intentos + 1))
  if [ "$intentos" -ge 15 ]; then
    echo "[radica] No fue posible migrar la base de datos." >&2
    exit 1
  fi
  echo "[radica] Esperando la base de datos ($intentos/15)..."
  sleep 3
done

python manage.py collectstatic --noinput

# Si se pasó un comando (p. ej. «python manage.py test»), se ejecuta ese en lugar del servidor.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

if [ "${SEED_DEMO:-0}" = "1" ]; then
  python manage.py seed_demo --solo-si-vacio
fi

exec gunicorn radica.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --access-logfile - --error-logfile -
