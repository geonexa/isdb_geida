"""
Celery app for background work (analysis module runs).

    redis-server                                   # broker (brew services start redis / apt)
    celery -A config worker -l info --pool solo    # macOS dev: one run at a time
    celery -A config worker -l info -c 2           # Linux server: two runs in parallel

Settings come from Django settings with the CELERY_ prefix (see settings.py).
"""
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("geida")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
