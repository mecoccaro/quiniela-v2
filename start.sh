#!/bin/bash
set -e
if [ "$SERVICE_TYPE" = "celery" ]; then
    exec uv run celery -A quiniela worker --loglevel=info --concurrency=2
else
    exec uv run gunicorn quiniela.wsgi:application --workers 2 --bind 0.0.0.0:$PORT
fi
