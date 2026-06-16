import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'inv.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()
if not User.objects.filter(username='mtirop').exists():
    User.objects.create_superuser('mtirop', 'mtirop345@gmail.com', '12345678')
    print("Superuser created successfully")
else:
    print("Superuser already exists")
