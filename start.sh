#!/bin/bash
set -e

# Detect service type from:
# 1. Explicit SERVICE_TYPE env var (manual override)
# 2. RAILWAY_SERVICE_NAME (auto-injected by Railway per service)
SERVICE_NAME="${SERVICE_TYPE:-$RAILWAY_SERVICE_NAME}"

if [ "$SERVICE_NAME" = "celery" ] || [ "$SERVICE_NAME" = "worker" ] || [ "$SERVICE_NAME" = "celery-worker" ]; then
    exec uv run celery -A quiniela worker --loglevel=info --concurrency=2
else
    exec uv run gunicorn quiniela.wsgi:application --workers 2 --bind 0.0.0.0:$PORT
fi
