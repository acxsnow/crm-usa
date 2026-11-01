#!/bin/sh
# Arranque en Render. Celery corre dentro del mismo servicio web para no pagar un
# worker aparte (RUN_EMBEDDED_WORKER=false lo apaga cuando exista uno propio).
# Si el servicio está dormido (plan gratis), las tareas tampoco corren.
set -e
alembic upgrade head
python -m scripts.seed --demo-org
if [ "${RUN_EMBEDDED_WORKER:-true}" = "true" ]; then
  celery -A app.workers.celery_app worker --beat --pool=solo --loglevel=info --schedule=/tmp/celerybeat-schedule &
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
