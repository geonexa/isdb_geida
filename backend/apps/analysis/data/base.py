import contextlib
import fcntl
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

from django.conf import settings


class DatasetUnavailable(Exception):
    pass


def part_path(out, suffix=None):
    """A temporary name next to `out`, unique to this call: a file is written there whole, then renamed
    onto `out`. Two runs fetching the same clip at once (the worker runs several) never write one file."""
    out = Path(out)
    suffix = out.suffix if suffix is None else suffix
    return out.with_name(f"{out.name}.{os.getpid()}-{uuid.uuid4().hex[:8]}.part{suffix}")


@contextlib.contextmanager
def cache_lock(out):
    """Hold an exclusive lock on `out` while it is produced, across processes: a second run asking for
    the same clip waits, then finds it in the cache instead of fetching it again."""
    lock = Path(f"{out}.lock")
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


class Dataset:
    id = ""
    title = ""
    kind = "raster"  # raster | vector
    resolution = ""
    version = ""
    reference_date = ""
    citation = ""
    licence = ""
    source = ""

    def covers(self, iso3):
        """Whether the dataset can serve this country (global datasets: always)."""
        return True

    # Local override ----------------------------------------------------------------
    @property
    def local_dir(self):
        return Path(settings.DATA_DIR) / "datasets" / self.id

    def local_files(self, iso3, year=None):
        """Local override files: <ISO3>_<year>.tif for one period, <ISO3>.tif, or shared mosaics."""
        d = self.local_dir
        if not d.exists():
            return []
        ext = ".tif" if self.kind == "raster" else ".geojson"
        if year is not None and (d / f"{iso3.upper()}_{year}{ext}").exists():
            return [d / f"{iso3.upper()}_{year}{ext}"]
        own = d / f"{iso3.upper()}{ext}"
        if own.exists():
            return [own]
        # shared mosaics, not other countries' files (XXX.tif, XXX_2020.tif)
        return sorted(p for p in d.glob(f"*{ext}") if not re.fullmatch(r"[A-Z]{3}(_\w+)?", p.stem))

    # Cache -------------------------------------------------------------------------
    def cache_path(self, bbox, iso3, suffix):
        key = hashlib.sha1(json.dumps([self.id, self.version, iso3, [round(v, 5) for v in bbox]]).encode()).hexdigest()[:16]
        p = Path(settings.DATA_DIR) / self.id / f"{iso3}_{key}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def fetch(self, bbox, iso3, log=print):
        """Return a local file clipped to bbox: GeoTIFF (raster) or GeoJSON (vector)."""
        raise NotImplementedError

    def describe(self):
        return {"id": self.id, "title": self.title, "kind": self.kind, "resolution": self.resolution,
                "version": self.version, "reference_date": self.reference_date, "citation": self.citation,
                "licence": self.licence, "source": self.source}
