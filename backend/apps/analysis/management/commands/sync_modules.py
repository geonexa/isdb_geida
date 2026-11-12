from django.core.management.base import BaseCommand

from apps.analysis.core.registry import sync_modules


class Command(BaseCommand):
    help = "Register the analysis modules found in backend/modules/."

    def handle(self, *args, **opts):
        for mid, m in sync_modules().items():
            self.stdout.write(f"{mid} {m['version']}: {m['title']}")
