FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
# Tolera finales de línea de Windows en el script de arranque
RUN sed -i 's/\r$//' docker/entrypoint.sh && chmod +x docker/entrypoint.sh \
    && mkdir -p /app/media /app/staticfiles

EXPOSE 8000
ENTRYPOINT ["./docker/entrypoint.sh"]
