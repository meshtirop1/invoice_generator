import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Creates a superuser from DJANGO_SUPERUSER_USERNAME / _EMAIL / _PASSWORD. '
        'Does nothing unless a password is supplied, so a public deployment can '
        'never come up with a known default login.'
    )

    def handle(self, *args, **kwargs):
        User = get_user_model()

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME', '').strip()
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '').strip()
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')

        if not username or not password:
            self.stdout.write(self.style.WARNING(
                'Skipped: set DJANGO_SUPERUSER_USERNAME and '
                'DJANGO_SUPERUSER_PASSWORD to create one.'
            ))
            return

        if User.objects.filter(username=username).exists():
            self.stdout.write(self.style.WARNING(
                f'Superuser "{username}" already exists — leaving it alone.'
            ))
            return

        User.objects.create_superuser(username, email or None, password)
        self.stdout.write(self.style.SUCCESS(f'Superuser "{username}" created.'))
