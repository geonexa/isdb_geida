"""Seeding from the reference catalogue: reading, running loaders, publishing, recording, skipping unchanged data."""
import io
import unittest
import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.projects.models import CRI
from apps.reference.catalog import CatalogError, read_catalog
from apps.reference.models import ReferenceDataset

CSV = ("cri_code,group_no,group_name,indicator_name,unit,per_annum,sex_disaggregated,geida_role,candidate_module,notes,library_version\n"
       "1.1,1,Energy,Households connected,Number,no,no,estimate,,,test\n"
       "2.2,2,Transport,Roads built,km,no,no,verify,,,test\n")


def entry(id, **kw):
    return {"id": id, "title": id.title(), "version": "1", "status": "ready", "required": True, **kw}


class SeedTests(TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="geida-seed-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.ref = self.tmp / "static"
        (self.ref / "data").mkdir(parents=True)
        (self.ref / "CRI_folder").mkdir(parents=True)
        (self.ref / "data" / "cri.csv").write_text(CSV)
        (self.ref / "data" / "rules.yaml").write_text("version: 1\n")
        (self.ref / "data" / "outline.geojson").write_text('{"type": "FeatureCollection", "features": []}')
        (self.ref / "CRI_folder" / "big.csv").write_text(CSV)
        self.published = self.tmp / "web" / "outline.geojson"
        self.write(self.ref, [
            entry("cri_small", folder="data", files=[{"path": "data/cri.csv"}],
                  load={"kind": "command", "command": "load_cri", "args": {"path": "data/cri.csv"}},
                  database={"table": "projects_cri", "model": "projects.CRI"}),
            entry("rules", files=[{"path": "data/rules.yaml"}], load={"kind": "runtime"}),
            entry("outline", files=[{"path": "data/outline.geojson"}], load={"kind": "publish", "to": str(self.published)}),
            entry("cri_big", folder="CRI_folder", required=False, large=True, files=[{"path": "CRI_folder/big.csv"}],
                  load={"kind": "command", "command": "load_cri", "args": {"path": "CRI_folder/big.csv"}},
                  database={"table": "projects_cri", "model": "projects.CRI"}),
            entry("later", required=False, files=[], load={"kind": "pending", "note": "not yet"}),
            entry("unknown_source", status="on_hold", hold_reason="no licence", files=[], load={"kind": "pending"}),
        ])
        self.enterContext(self.settings(REFERENCE_DATA_DIR=self.ref))

    def write(self, folder, datasets):
        (folder / "catalog.json").write_text(json.dumps({"schema_version": 1, "datasets": datasets}))

    def seed(self, *args, **kw):
        out = io.StringIO()
        call_command("seed", *args, stdout=out, stderr=io.StringIO(), **kw)
        return out.getvalue()

    def test_required_seeds_load_publish_and_are_recorded(self):
        out = self.seed()
        self.assertEqual(CRI.objects.count(), 2)
        self.assertTrue(self.published.exists())
        self.assertNotIn("cri_big", out)  # not required: only with --only
        status = {r.dataset: r.status for r in ReferenceDataset.objects.all()}
        self.assertEqual(status, {"analysis_modules": "loaded", "cri_small": "loaded", "rules": "checked", "outline": "published"})
        self.assertEqual(ReferenceDataset.objects.get(dataset="analysis_modules").catalog, "registry")
        rec = ReferenceDataset.objects.get(dataset="cri_small")
        self.assertEqual((rec.rows, rec.table, rec.catalog), (2, "projects_cri", "reference"))
        self.assertEqual(len(rec.files), 1)
        self.assertEqual(len(rec.fingerprint), 64)

    def test_large_dataset_is_recorded_then_skipped_until_forced(self):
        self.seed()  # CRI table now has rows
        self.assertIn("already in the database", self.seed("--only", "cri_big"))
        self.assertEqual(ReferenceDataset.objects.filter(dataset="cri_big").first().status, "recorded")
        self.assertIn("up to date", self.seed("--only", "cri_big"))
        self.assertIn("load_cri", self.seed("--only", "cri_big", "--force"))
        self.assertEqual(ReferenceDataset.objects.filter(dataset="cri_big").first().status, "loaded")
        # Changed files (new fingerprint) are loaded again without --force.
        (self.ref / "CRI_folder" / "big.csv").write_text(CSV + "3.3,3,Water,Points,Number,no,no,context,,,test\n")
        self.assertIn("load_cri", self.seed("--only", "cri_big"))
        self.assertEqual(CRI.objects.count(), 3)

    def test_path_override_pending_and_on_hold(self):
        other = self.tmp / "elsewhere"
        other.mkdir()
        (other / "big.csv").write_text(CSV)
        out = self.seed("--only", "cri_big", "--path", str(other), "--force")
        self.assertIn(str(other / "big.csv"), out)
        self.assertEqual(ReferenceDataset.objects.first().folder, str(other))
        self.assertIn("loader not built yet: not yet", self.seed("--only", "later"))
        self.assertIn("on hold: no licence", self.seed("--only", "unknown_source"))

    def test_errors(self):
        with self.assertRaisesMessage(CommandError, "Unknown dataset(s): nope"):
            self.seed("--only", "nope")
        with self.assertRaisesMessage(CommandError, "--path needs exactly one dataset"):
            self.seed("--path", "/tmp")
        (self.ref / "data" / "cri.csv").unlink()
        with self.assertRaisesMessage(CommandError, "1 dataset(s) failed"):
            self.seed("--only", "cri_small")
        self.assertEqual(ReferenceDataset.objects.first().status, "failed")

    def test_list_and_dry_run(self):
        out = self.seed("list")
        for ds in ("analysis_modules", "cri_small", "rules", "outline", "cri_big", "later", "unknown_source"):
            self.assertIn(ds, out)
        self.seed("--dry-run")
        self.assertFalse(ReferenceDataset.objects.exists())
        self.assertFalse(self.published.exists())

    def test_catalog_validation(self):
        self.write(self.ref, [entry("a", load={"kind": "magic"})])
        with self.assertRaisesMessage(CatalogError, "load kind 'magic'"):
            read_catalog("reference", self.ref / "catalog.json")
        self.write(self.ref, [entry("a"), entry("a")])
        with self.assertRaisesMessage(CatalogError, "listed twice"):
            read_catalog("reference", self.ref / "catalog.json")

    def test_dataset_file_and_missing_catalogue(self):
        from apps.reference.catalog import dataset_file
        self.assertEqual(dataset_file("rules"), (self.ref / "data" / "rules.yaml").resolve())
        with self.assertRaisesMessage(CatalogError, "isn't in"):
            dataset_file("nope")
        with self.settings(REFERENCE_DATA_DIR=self.tmp / "missing"), self.assertRaisesMessage(CommandError, "catalogue not found"):
            self.seed("list")


@unittest.skipUnless((Path(settings.REFERENCE_DATA_DIR) / "catalog.json").exists(), "no REFERENCE_DATA_DIR on this machine")
class RealCatalogTests(TestCase):
    def test_reference_catalog_is_valid_and_its_small_files_exist(self):
        datasets = {d.id: d for d in read_catalog("reference", Path(settings.REFERENCE_DATA_DIR) / "catalog.json")}
        for ds in ("cri", "member_countries", "osm_taxonomy", "gadm"):
            self.assertIn(ds, datasets)
            self.assertEqual(datasets[ds].missing_files(), [], ds)
