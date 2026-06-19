#!/bin/sh
# Entrypoint script: run migrations, then start API
echo "Running migrations..."
alembic upgrade head
echo "Starting API..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
