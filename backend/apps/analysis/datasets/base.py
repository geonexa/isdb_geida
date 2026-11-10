import hashlib
import json
from pathlib import Path

from django.conf import settings


class DatasetUnavailable(Exception):
    pass


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

    def local_files(self, iso3):
        d = self.local_dir
        if not d.exists():
            return []
        ext = ".tif" if self.kind == "raster" else ".geojson"
        own = d / f"{iso3.upper()}{ext}"
        if own.exists():
            return [own]
        return sorted(p for p in d.glob(f"*{ext}") if len(p.stem) != 3)  # shared mosaics, not other countries

    # Cache -------------------------------------------------------------------------
    def cache_path(self, bbox, iso3, suffix):
        key = hashlib.sha1(json.dumps([self.id, self.version, iso3, [round(v, 5) for v in bbox]]).encode()).hexdigest()[:16]
        p = Path(settings.DATA_DIR) / "cache" / self.id / f"{iso3}_{key}{suffix}"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def fetch(self, bbox, iso3, log=print):
        """Return a local file clipped to bbox: GeoTIFF (raster) or GeoJSON (vector)."""
        raise NotImplementedError

    def describe(self):
        return {"id": self.id, "title": self.title, "kind": self.kind, "resolution": self.resolution,
                "version": self.version, "reference_date": self.reference_date, "citation": self.citation,
                "licence": self.licence, "source": self.source}
