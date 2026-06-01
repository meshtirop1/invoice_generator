#!/bin/sh

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating default superuser..."
python manage.py create_default_superuser

echo "Starting server..."
exec gunicorn inv.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120 --access-logfile - --error-logfile -
