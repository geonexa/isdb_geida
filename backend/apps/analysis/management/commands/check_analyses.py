"""Validate every analysis folder, the categories and the planned list.

    python manage.py check_analyses          # errors make the command fail (exit code 1)
    python manage.py check_analyses --env    # also list the engines available on this machine
"""
from django.core.management.base import BaseCommand, CommandError

from apps.analysis.core.envcheck import engines
from apps.analysis.core.registry import (analyses_dir, analysis_folders, load_run_function, read_categories,
                                         read_manifests, read_planned)
from apps.analysis.data import DATASETS


class Command(BaseCommand):
    help = "Check analyses/: manifests, run functions, datasets, legends, docs, tests, planned list."

    def add_arguments(self, parser):
        parser.add_argument("--env", action="store_true", help="also report engines (GDAL, GRASS, WhiteboxTools)")

    def handle(self, *args, env=False, **opts):
        errors, warnings = [], []
        root = analyses_dir()
        try:
            cats = read_categories()
        except Exception as exc:  # noqa: BLE001
            raise CommandError(f"categories.yaml: {exc}")
        manifests = read_manifests(errors)
        try:
            planned = read_planned(built=set(manifests))
        except ValueError as exc:
            errors.append(str(exc))
            planned = []

        folders = analysis_folders()
        have = engines()
        for aid, m in sorted(manifests.items()):
            folder = folders[aid]
            rel = folder.relative_to(root.parent)
            try:
                load_run_function(aid)
            except Exception as exc:  # noqa: BLE001 (syntax errors, missing run)
                errors.append(f"{rel}/run.py: {exc}")
            for group in ("required", "optional"):
                for inp in m.get("inputs", {}).get(group, []) or []:
                    ds = inp.get("default")
                    if ds and ds not in DATASETS and inp.get("source") != "project_area":
                        (errors if group == "required" else warnings).append(
                            f"{rel}: input '{inp['name']}' uses dataset '{ds}', which isn't registered")
            for o in m.get("outputs", []) or []:
                if o.get("legend") and not (folder / o["legend"]).exists():
                    errors.append(f"{rel}: output '{o['name']}' legend file {o['legend']} is missing")
            if not (folder / "METHOD.md").exists():
                warnings.append(f"{rel}: no METHOD.md (method, data, limitations)")
            tests = folder / "tests"
            if not any(tests.glob("test*.py")) if tests.exists() else True:
                warnings.append(f"{rel}: no tests/ (python manage.py test analyses.{folder.parent.name}.{aid})")
            elif not ((folder / "__init__.py").exists() and (folder.parent / "__init__.py").exists()
                      and (tests / "__init__.py").exists()):
                warnings.append(f"{rel}: tests won't be found without __init__.py in the category, analysis and tests folders")
            for e in m.get("requires", []) or []:
                if not have.get(e, (False,))[0]:
                    warnings.append(f"{rel}: needs {e}, not available here ({have[e][1]}); listed as not available")

        self.stdout.write(f"Analyses: {len(manifests)} in {len({m['category'] for m in manifests.values()})} "
                          f"of {len(cats)} categories · planned: {len(planned)}")
        if env:
            self.stdout.write("Engines:")
            for name, (ok, detail) in have.items():
                self.stdout.write(f"  {'✓' if ok else '✗'} {name:9} {detail}")
        for w in warnings:
            self.stdout.write(self.style.WARNING(f"warning: {w}"))
        for e in errors:
            self.stdout.write(self.style.ERROR(f"error: {e}"))
        if errors:
            raise CommandError(f"{len(errors)} error(s) in analyses/.")
        self.stdout.write(self.style.SUCCESS("All analyses are valid."))
