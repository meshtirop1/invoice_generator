from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Creates a default superuser if one does not already exist'

    def handle(self, *args, **kwargs):
        User = get_user_model()
        if not User.objects.filter(username='mtirop').exists():
            User.objects.create_superuser('mtirop', 'mtirop345@gmail.com', '12345678')
            self.stdout.write(self.style.SUCCESS('Superuser created successfully'))
        else:
            self.stdout.write(self.style.WARNING('Superuser already exists'))
