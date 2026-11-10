"""
Load GADM admin boundaries prepared by backend/scripts/prepare_gadm.py.

    python manage.py load_admin_units [--levels 0,1,2,3] [--countries UGA,AZE] [--replace]
    python manage.py load_admin_units --full ""      # simplified shapes only (quick dev load)
    python manage.py load_admin_units --full /path/a.gpkg --simplified /path/b.gpkg

Both files have layers adm0..adm3. --simplified alone also works (the
simplified geometry is then used for both columns, e.g. for a quick dev load).
By default both files are read from backend/data/boundaries/
(settings.DATA_DIR); GADM_GPKG / GADM_GPKG_SIMPLIFIED in .env override that.
"""
import os
import re

from django.conf import settings
from django.contrib.gis.gdal import DataSource
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.boundaries.models import AdminUnit

BATCH = 500
# PostgreSQL rejects a message over 1 GB and drops the connection. Full-resolution
# countries (adm0) reach that well before 500 rows, so a batch is also flushed by
# geometry size (WKB bytes; the query carries them hex-encoded, about twice that).
BATCH_BYTES = 64 * 1024 * 1024
GID_RE = re.compile(r"^[A-Z0-9]{3}(\.[0-9.]+_\d+)?$")
BOUNDARIES = settings.DATA_DIR / "boundaries"
DEFAULT_FULL = os.environ.get("GADM_GPKG") or str(BOUNDARIES / "gadm41_adm0-3.gpkg")
DEFAULT_SIMPLIFIED = os.environ.get("GADM_GPKG_SIMPLIFIED") or str(BOUNDARIES / "gadm41_adm0-3_simplified.gpkg")
TEXT_FIELDS = ("name_local", "type", "parent_gid", "name_1", "name_2", "name_3", "hasc")


def _multi(geom):
    geom = GEOSGeometry(geom.wkb, srid=4326) if not isinstance(geom, GEOSGeometry) else geom
    if geom.geom_type == "Polygon":
        geom = MultiPolygon(geom, srid=4326)
    return geom


def _layer(path, name):
    ds = DataSource(path)
    for layer in ds:
        if layer.name == name:
            return layer
    return None


class Command(BaseCommand):
    help = "Load GADM admin units (levels 0-3) into the AdminUnit table."

    def add_arguments(self, parser):
        parser.add_argument("--full", default=DEFAULT_FULL,
                            help='Full-resolution GeoPackage; pass --full "" to load only the simplified file')
        parser.add_argument("--simplified", default=DEFAULT_SIMPLIFIED)
        parser.add_argument("--levels", default="0,1,2,3")
        parser.add_argument("--countries", default="", help="Comma-separated ISO3 codes (default: all in the file)")
        parser.add_argument("--replace", action="store_true", help="Delete the matching units first")

    def handle(self, *args, **opts):
        full, simple = opts["full"], opts["simplified"]
        if not (full or simple):
            raise CommandError("Pass --full and/or --simplified, or put the files in backend/data/boundaries/.")
        for p in (full, simple):
            if p and not os.path.exists(p):
                raise CommandError(f"File not found: {p}")
        levels = [int(x) for x in opts["levels"].split(",") if x.strip()]
        countries = {c.strip().upper() for c in opts["countries"].split(",") if c.strip()}

        for level in levels:
            name = f"adm{level}"
            display = {}
            if simple:
                lyr = _layer(simple, name)
                if lyr is None:
                    raise CommandError(f"Layer {name} not found in {simple}")
                for f in lyr:
                    if countries and f.get("iso3") not in countries:
                        continue
                    display[f.get("gid")] = _multi(f.geom.geos)
            source = full or simple
            lyr = _layer(source, name)
            if lyr is None:
                raise CommandError(f"Layer {name} not found in {source}")

            with transaction.atomic():
                qs = AdminUnit.objects.filter(level=level)
                if countries:
                    qs = qs.filter(iso3__in=countries)
                if opts["replace"]:
                    deleted = qs.delete()[0]
                    self.stdout.write(f"{name}: removed {deleted}")
                # gid is unique across all levels, so check against everything loaded.
                existing = set(AdminUnit.objects.values_list("gid", flat=True))
                batch, batch_bytes, created, skipped, bad = [], 0, 0, 0, 0
                for f in lyr:
                    iso3 = f.get("iso3")
                    if countries and iso3 not in countries:
                        continue
                    gid = f.get("gid")
                    if not gid or not GID_RE.match(gid):
                        bad += 1  # GADM placeholders such as Ukraine's "?" unit
                        continue
                    if gid in existing:
                        skipped += 1
                        continue
                    existing.add(gid)
                    geom = _multi(f.geom.geos) if full else display.get(gid)
                    if geom is None or geom.empty:
                        skipped += 1
                        self.stderr.write(f"{name}: {gid} has no geometry; skipped")
                        continue
                    unit = AdminUnit(
                        gid=gid,
                        level=level,
                        iso3=iso3,
                        country=f.get("country") or "",
                        name=f.get("name") or gid,
                        disputed=bool(f.get("disputed")),
                        area_km2=f.get("area_km2") or 0,
                        geom=geom,
                        geom_display=display.get(gid),
                        **{k: (f.get(k) or "") for k in TEXT_FIELDS},
                    )
                    batch.append(unit)
                    batch_bytes += len(geom.wkb) + (len(unit.geom_display.wkb) if unit.geom_display else 0)
                    if len(batch) >= BATCH or batch_bytes >= BATCH_BYTES:
                        AdminUnit.objects.bulk_create(batch)
                        created += len(batch)
                        batch, batch_bytes = [], 0
                        if created % 10_000 == 0:
                            self.stdout.write(f"{name}: {created:,} loaded…")
                if batch:
                    AdminUnit.objects.bulk_create(batch)
                    created += len(batch)
            msg = f"{name}: loaded {created}, skipped {skipped} existing"
            if bad:
                msg += f", ignored {bad} without a valid GADM id"
            self.stdout.write(self.style.SUCCESS(msg))
