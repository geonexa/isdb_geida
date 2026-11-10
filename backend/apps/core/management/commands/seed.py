"""
Load the reference data GEIDA needs into a database, after `migrate`.

    python manage.py seed                       # CRI library + analysis modules
    python manage.py seed --boundaries          # + GADM admin units (large, slow)
    python manage.py seed --boundaries --countries UGA,AZE,MLI

Every step is idempotent, so the command is safe to re-run after a deploy. Role
groups (GEIDA reviewers / analysts) come from a data migration, not from here.
See seeds/README.md for what each step loads and where its files live.
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Load reference data (CRI library, analysis modules, optionally admin boundaries)."

    def add_arguments(self, parser):
        parser.add_argument("--boundaries", action="store_true",
                            help="Also load GADM admin units from DATA_DIR/boundaries/ (several GB).")
        parser.add_argument("--countries", default="",
                            help="With --boundaries: comma-separated ISO3 codes (default: all).")

    def handle(self, *args, boundaries=False, countries="", **opts):
        steps = [
            ("CRI library", lambda: call_command("load_cri", stdout=self.stdout)),
            ("Analysis modules", lambda: call_command("sync_modules", stdout=self.stdout)),
        ]
        if boundaries:
            steps.append(("Admin boundaries", lambda: call_command(
                "load_admin_units", countries=countries, stdout=self.stdout)))
        for i, (name, run) in enumerate(steps, 1):
            self.stdout.write(self.style.MIGRATE_HEADING(f"[{i}/{len(steps)}] {name}"))
            run()
        if not boundaries:
            self.stdout.write(
                f"Admin boundaries skipped (add --boundaries to load GADM from "
                f"{settings.DATA_DIR / 'boundaries'})."
            )
        self.stdout.write(self.style.SUCCESS("Seed complete."))
