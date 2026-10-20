"""Settings the live site runs with (DJANGO_SETTINGS_MODULE=inv.prod_settings in the server's
env file): the normal settings plus the app-wide password gate (inv/gate.py)."""
from .settings import *  # noqa: F401,F403

MIDDLEWARE = [*MIDDLEWARE, 'inv.gate.GatePasswordMiddleware']  # noqa: F405
