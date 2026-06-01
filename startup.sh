#!/bin/sh
set -e

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Creating default superuser..."
python manage.py create_default_superuser || echo "Superuser step skipped"

echo "==> Starting gunicorn..."
exec gunicorn inv.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile -
