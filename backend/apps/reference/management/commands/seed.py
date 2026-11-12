"""
Seed a GEIDA database from the reference data catalogue, REFERENCE_DATA_DIR/catalog.json
(see the README.md next to it), and register the analyses in backend/analyses/:

    python manage.py seed list                     # every dataset: catalogue, status, files, rows, last load
    python manage.py seed                          # everything marked required (a new installation)
    python manage.py seed --only gadm,cri          # chosen datasets
    python manage.py seed --only gadm --path /other/disk/Admin_Boundaries
    python manage.py seed --only gadm --countries UGA,AZE    # passed to load_admin_units
    python manage.py seed --dry-run                # what would be done

The analysis registry (sync_modules) runs on every seed. Small datasets (CRI library) are
re-applied on every run (idempotent loaders). Large datasets (GADM, HydroATLAS: `large: true`, or
anything with a database table and over 50 MB of files) are loaded once: a later run skips them
while their files are unchanged (same fingerprint), unless --force. A large dataset already in the
database with no load recorded is recorded rather than reloaded. Every step is recorded in
reference.ReferenceDataset.
"""
import getpass
import shutil

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.reference.catalog import CatalogError, read_all
from apps.reference.models import ReferenceDataset

REGISTRY = "analysis_modules"  # built-in step: register backend/analyses/ (not a catalogue dataset)


class Command(BaseCommand):
    help = "Seed the database from REFERENCE_DATA_DIR/catalog.json and register the analyses."

    def add_arguments(self, parser):
        parser.add_argument("action", nargs="?", default="run", choices=["run", "list"])
        parser.add_argument("--only", default="", help="Comma-separated dataset ids (default: every required dataset)")
        parser.add_argument("--path", default="", help="With one --only: read its files from this folder instead")
        parser.add_argument("--countries", default="", help="ISO3 codes for admin boundaries (load_admin_units)")
        parser.add_argument("--force", action="store_true", help="Reload large datasets even if unchanged")
        parser.add_argument("--dry-run", action="store_true", help="Show what would be done")

    def handle(self, *args, action, only, path, countries, force, dry_run, **opts):
        try:
            datasets = read_all()
        except CatalogError as exc:
            raise CommandError(str(exc))
        by_id = {d.id: d for d in datasets}
        if action == "list":
            return self.list(datasets)

        ids = [i.strip() for i in only.split(",") if i.strip()]
        unknown = [i for i in ids if i not in by_id and i != REGISTRY]
        if unknown:
            raise CommandError(f"Unknown dataset(s): {', '.join(unknown)}. Known: {', '.join(sorted(by_id))}.")
        if path and len(ids) != 1:
            raise CommandError("--path needs exactly one dataset in --only.")
        chosen = [by_id[i] for i in ids if i != REGISTRY] if ids else [d for d in datasets if d.required and d.status != "on_hold"]
        run_registry = not ids or REGISTRY in ids

        failures = 0
        total = len(chosen) + run_registry
        if run_registry:
            self.stdout.write(self.style.MIGRATE_HEADING(f"[1/{total}] {REGISTRY} · analyses in backend/analyses/ (registry)"))
            if dry_run:
                self.stdout.write("  manage.py sync_modules")
            else:
                call_command("sync_modules", stdout=self.stdout)
                from apps.analysis.models import Module
                ReferenceDataset.objects.create(
                    catalog="registry", dataset=REGISTRY, title="Analysis catalogue (registered analyses)", status="loaded",
                    folder=str(settings.ANALYSES_DIR), rows=Module.objects.filter(active=True).count(), table="analysis_module",
                    loaded_by=getpass.getuser())
        for n, d in enumerate(chosen, 1 + run_registry):
            self.stdout.write(self.style.MIGRATE_HEADING(f"[{n}/{total}] {d.id} · {d.title}"))
            try:
                self.seed_one(d, path or None, countries, force, dry_run, explicit=bool(ids))
            except Exception as exc:  # keep going; report at the end
                failures += 1
                self.stderr.write(self.style.ERROR(f"  failed: {exc}"))
                if not dry_run:
                    self.record(d, "failed", path or None, report=str(exc))
        if failures:
            raise CommandError(f"{failures} dataset(s) failed.")
        self.stdout.write(self.style.SUCCESS("Seed complete." if not dry_run else "Dry run: nothing changed."))

    # ------------------------------------------------------------------------------------
    def seed_one(self, d, folder, countries, force, dry_run, explicit):
        load = d.load
        kind = load.get("kind", "pending")
        if d.status == "on_hold":
            self.stdout.write(self.style.WARNING(f"  on hold: {d.entry.get('hold_reason', '')}"))
            return
        if kind == "pending":
            self.stdout.write(self.style.WARNING(f"  loader not built yet{': ' + load['note'] if load.get('note') else ''}"))
            return
        missing = d.missing_files(folder)
        if missing:
            raise CommandError(f"files missing in {folder or d.root}: {', '.join(missing)}")

        if kind == "runtime":
            self.stdout.write(f"  read at run time ({load.get('note', '')}); files present")
            if not dry_run:
                self.record(d, "checked", folder)
            return

        if kind == "publish":
            src = next(p for _, found in d.files(folder) for p in found if p)
            dest = settings.BASE_DIR.parent / load["to"]  # relative to the repository (an absolute path also works)
            same = dest.exists() and dest.read_bytes() == src.read_bytes()
            self.stdout.write(f"  {'up to date' if same else 'copy'}: {src.name} → {load['to']}")
            if not dry_run and not same:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
            if not dry_run:
                self.record(d, "published", folder)
            return

        # kind == "command"
        fingerprint, _ = d.fingerprint(folder)
        model = d.model
        if d.large and not force:
            last = ReferenceDataset.objects.filter(dataset=d.id, status__in=("loaded", "recorded")).first()
            if last and last.fingerprint == fingerprint:
                self.stdout.write(f"  up to date (loaded {last.loaded:%Y-%m-%d}, {last.rows or 0:,} rows); --force to reload")
                return
            if not last and model is not None and model.objects.exists():
                rows = model.objects.count()
                self.stdout.write(f"  already in the database ({rows:,} rows in {d.table}): recorded, not reloaded; --force to reload")
                if not dry_run:
                    self.record(d, "recorded", folder, rows=rows)
                return
        args = d.resolved_args(folder)
        if countries and load["command"] == "load_admin_units":
            args["countries"] = countries
        shown = " ".join(f"--{k}={v}" for k, v in args.items())
        self.stdout.write(f"  manage.py {load['command']} {shown}")
        if dry_run:
            return
        call_command(load["command"], stdout=self.stdout, **args)
        rows = model.objects.count() if model is not None else None
        self.record(d, "loaded", folder, rows=rows)
        if rows is not None:
            self.stdout.write(f"  {rows:,} rows in {d.table}")

    def record(self, d, status, folder, rows=None, report=""):
        fingerprint, files = d.fingerprint(folder)
        ReferenceDataset.objects.create(
            catalog=d.catalog, dataset=d.id, version=d.version, title=d.title, status=status,
            folder=str(folder or d.path(d.entry.get("folder") or ".")), files=files, fingerprint=fingerprint,
            features=d.entry.get("features") or {}, rows=rows, table=d.table, source=d.entry.get("source") or {},
            report=report, loaded_by=getpass.getuser())

    # ------------------------------------------------------------------------------------
    def list(self, datasets):
        from apps.analysis.models import Module
        latest = {}
        for r in ReferenceDataset.objects.all():
            latest.setdefault(r.dataset, r)
        head = f"{'catalog':10} {'id':18} {'status':8} {'req':4} {'load':8} {'files':9} {'rows':>11}  last load"
        self.stdout.write(head)
        self.stdout.write("-" * len(head))
        last = latest.get(REGISTRY)
        self.stdout.write(f"{'registry':10} {REGISTRY:18} {'ready':8} {'yes':4} {'command':8} {'':9} "
                          f"{Module.objects.filter(active=True).count():>11,}  {f'{last.status} {last.loaded:%Y-%m-%d}' if last else 'never'}")
        for d in datasets:
            files = d.files()
            expected = sum(len(f) for _, f in files) or len(files)
            present = sum(1 for _, f in files for p in f if p)
            model = d.model
            rows = f"{model.objects.count():,}" if model is not None else "—"
            last = latest.get(d.id)
            when = f"{last.status} {last.loaded:%Y-%m-%d}" if last else "never"
            self.stdout.write(f"{d.catalog:10} {d.id:18} {d.status:8} {'yes' if d.required else 'no':4} "
                              f"{d.load.get('kind', 'pending'):8} {present:>3}/{expected:<5} {rows:>11}  {when}")
