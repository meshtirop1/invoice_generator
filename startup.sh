#!/bin/sh

echo "Running migrations..."
python manage.py migrate --noinput

echo "Creating superuser if not exists..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='mtirop').exists():
    User.objects.create_superuser('mtirop', 'mtirop345@gmail.com', '12345678')
    print('Superuser created successfully')
else:
    print('Superuser already exists')
"

echo "Starting server..."
exec gunicorn inv.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120 --access-logfile - --error-logfile -
