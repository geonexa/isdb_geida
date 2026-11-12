"""
The reference data catalogue: REFERENCE_DATA_DIR/catalog.json (default geida_static_data/ next to
the repository). One folder per dataset next to it, and one entry per dataset with its files,
database table, how to load it (`load`), source, licence and status (format: the `conventions`
block in the file). Read by `manage.py seed` and by the app for files it reads at run time
(`dataset_file("member_countries")`, `dataset_file("osm_taxonomy")`).
"""
import glob
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

LOAD_KINDS = ("command", "publish", "runtime", "pending")


class CatalogError(Exception):
    pass


@dataclass
class Dataset:
    catalog: str            # seeds | reference
    root: Path              # folder holding the catalogue (paths are relative to it)
    entry: dict = field(repr=False)

    @property
    def id(self):
        return self.entry["id"]

    @property
    def title(self):
        return self.entry.get("title", self.id)

    @property
    def version(self):
        return str(self.entry.get("version") or "")

    @property
    def status(self):
        return self.entry.get("status", "ready")

    @property
    def required(self):
        return bool(self.entry.get("required"))

    @property
    def large(self):
        """Loaded once and skipped while unchanged: `large: true`, or a table fed from over 50 MB of files."""
        if "large" in self.entry:
            return bool(self.entry["large"])
        if not self.table:
            return False
        return sum(p.stat().st_size for _, found in self.files() for p in found if p and p.is_file()) > 50 * 1024 ** 2

    @property
    def load(self):
        return self.entry.get("load") or {"kind": "pending"}

    @property
    def table(self):
        return (self.entry.get("database") or {}).get("table") or ""

    @property
    def model(self):
        label = (self.entry.get("database") or {}).get("model")
        if not label:
            return None
        from django.apps import apps
        try:
            return apps.get_model(label)
        except LookupError:  # the table isn't built yet (loader pending)
            return None

    def path(self, rel):
        """A catalogue path (relative to the catalogue folder) as an absolute path."""
        p = Path(rel)
        return p if p.is_absolute() else (self.root / p).resolve()

    def files(self, folder=None):
        """[(declared path or pattern, [existing absolute paths])] for every `files` entry.

        folder: read the dataset's files from another folder (seed --path) instead of the
        catalogue's `folder`.
        """
        out = []
        declared_folder = self.entry.get("folder") or ""
        for f in self.entry.get("files", []):
            rel = f.get("path") or f.get("pattern")
            if folder and declared_folder and rel.startswith(declared_folder.rstrip("/") + "/"):
                base = Path(folder) / rel[len(declared_folder.rstrip("/")) + 1:]
            else:
                base = self.path(rel)
            if "path" in f:
                out.append((rel, [base] if base.exists() else []))
                continue
            keys = f.get("levels") or f.get("regions")
            if keys:
                names = [str(base).format(level=k, region=k) if "levels" in f else str(base).format(region=k) for k in keys]
                out.append((rel, [Path(n) for n in names if Path(n).exists()]))
                missing = [n for n in names if not Path(n).exists()]
                if missing:
                    out[-1] = (rel, out[-1][1] + [None] * len(missing))  # None marks a missing expected file
            else:  # free pattern such as {category}/{id}
                found = sorted(Path(p) for p in glob.glob(re.sub(r"\{[^}]+\}", "*", str(base))))
                out.append((rel, found))
        return out

    def missing_files(self, folder=None):
        missing = []
        for rel, found in self.files(folder):
            if not found or None in found:
                missing.append(rel)
        return missing

    def fingerprint(self, folder=None):
        """SHA-256 over the names, sizes and modification dates of the files (fast, even for GBs)."""
        listing = []
        for _, found in self.files(folder):
            for p in found:
                if p is not None and p.is_file():
                    st = p.stat()
                    listing.append({"path": str(p), "bytes": st.st_size,
                                    "modified": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(timespec="seconds")})
        digest = hashlib.sha256(json.dumps(listing, sort_keys=True).encode()).hexdigest()
        return digest, listing

    def resolved_args(self, folder=None):
        """The `load.args`, with values that are paths made absolute (relative to the catalogue or `folder`)."""
        args = dict(self.load.get("args") or {})
        declared_folder = (self.entry.get("folder") or "").rstrip("/")
        for k, v in args.items():
            if isinstance(v, str) and ("/" in v or v.endswith((".csv", ".gpkg", ".shp", ".geojson", ".json", ".yaml"))):
                if folder and declared_folder and v.startswith(declared_folder + "/"):
                    args[k] = str(Path(folder) / v[len(declared_folder) + 1:])
                else:
                    args[k] = str(self.path(v))
        return args


def catalog_path():
    return Path(settings.REFERENCE_DATA_DIR) / "catalog.json"


def read_catalog(name, path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise CatalogError(f"Reference data catalogue not found: {path}. Copy geida_static_data/ next to the "
                           "repository or set REFERENCE_DATA_DIR in backend/.env.") from None
    except json.JSONDecodeError as exc:
        raise CatalogError(f"{path}: not valid JSON ({exc})") from None
    ids = set()
    out = []
    for entry in data.get("datasets", []):
        if "id" not in entry:
            raise CatalogError(f"{path}: a dataset has no id")
        if entry["id"] in ids:
            raise CatalogError(f"{path}: dataset id '{entry['id']}' is listed twice")
        kind = (entry.get("load") or {}).get("kind", "pending")
        if kind not in LOAD_KINDS:
            raise CatalogError(f"{path}: '{entry['id']}' has load kind '{kind}' (use one of {', '.join(LOAD_KINDS)})")
        if kind == "command" and not entry["load"].get("command"):
            raise CatalogError(f"{path}: '{entry['id']}' needs load.command")
        ids.add(entry["id"])
        out.append(Dataset(name, path.parent, entry))
    return out


def read_all():
    """Every dataset in the reference catalogue."""
    return read_catalog("reference", catalog_path())


_file_cache = {}


def dataset_file(dataset_id):
    """
    Absolute path of a dataset's (first) file, from the catalogue: how the app finds files it reads
    at run time, e.g. dataset_file("member_countries"). Raises CatalogError if it isn't listed.
    """
    path = catalog_path()
    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        key = None
    if key not in _file_cache:
        _file_cache.clear()
        _file_cache[key] = {d.id: d for d in read_catalog("reference", path)} if key else {}
    d = _file_cache[key].get(dataset_id)
    if d is None:
        raise CatalogError(f"Dataset '{dataset_id}' isn't in {path}.")
    rel = next((f["path"] for f in d.entry.get("files", []) if f.get("path")), None)
    if not rel:
        raise CatalogError(f"Dataset '{dataset_id}' lists no file path in {path}.")
    return d.path(rel)
