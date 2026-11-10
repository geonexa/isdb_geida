"""
Settings entry point: DJANGO_SETTINGS_MODULE stays "config.settings" everywhere
(manage.py, WSGI, Celery); DJANGO_ENV in .env picks the environment module.
"""
from .base import IS_PRODUCTION

if IS_PRODUCTION:
    from .production import *  # noqa: F401,F403
else:
    from .development import *  # noqa: F401,F403
