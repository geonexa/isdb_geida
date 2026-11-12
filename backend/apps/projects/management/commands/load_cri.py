"""
Load (or update) the IsDB Core Result Indicator library from the seed CSV.

    python manage.py load_cri [path/to/isdb_cri_2025_seed.csv]

CRI codes are data, not code: re-running updates existing rows by code.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.projects.models import CRI

def _default():
    from apps.reference.catalog import dataset_file
    return dataset_file("cri")  # REFERENCE_DATA_DIR/catalog.json; normally run through `manage.py seed`


def _sort_key(code):
    group, _, item = code.partition(".")
    return int(group) * 1000 + int(item or 0)


class Command(BaseCommand):
    help = "Load the IsDB CRI library from the seed CSV."

    def add_arguments(self, parser):
        parser.add_argument("path", nargs="?", default="")

    def handle(self, *args, path, **opts):
        p = Path(path) if path else _default()
        if not p.exists():
            raise CommandError(f"File not found: {p}")
        created = updated = 0
        with p.open(encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                code = row["cri_code"].strip()
                if not code:
                    continue
                values = {
                    "group_no": int(row["group_no"]),
                    "group_name": row["group_name"].strip(),
                    "name": row["indicator_name"].strip(),
                    "unit": row["unit"].strip(),
                    "per_annum": row["per_annum"].strip().lower() == "yes",
                    "sex_disaggregated": (row["sex_disaggregated"].strip().lower() or "no"),
                    "geida_role": (row["geida_role"].strip().lower() or "none"),
                    "candidate_module": row["candidate_module"].strip(),
                    "notes": row["notes"].strip(),
                    "library_version": row["library_version"].strip(),
                    "sort_key": _sort_key(code),
                }
                _, was_created = CRI.objects.update_or_create(code=code, defaults=values)
                created += was_created
                updated += not was_created
        self.stdout.write(self.style.SUCCESS(f"CRI library: {created} added, {updated} updated."))
