"""
Cache of derived products: rasters an analysis computes that others can reuse
(a conditioned DEM, flow accumulation, a land cover reclassification, ...).

The key is built from a name plus everything the result depends on (the input rasters'
dataset ids, periods and grids, parameters, a code version), so a change to any of them
makes a new entry. Entries live in DATA_DIR/derived/<name>/; the oldest are removed
when the folder grows past MAX_BYTES.
"""
import hashlib
import json
from pathlib import Path

from django.conf import settings

MAX_BYTES = 5 * 1024 ** 3


def key(name, parts):
    blob = json.dumps(parts, sort_keys=True, default=str)
    return f"{name}_{hashlib.sha1(blob.encode()).hexdigest()[:16]}"


def path_for(name, parts, suffix=".tif"):
    folder = Path(settings.DATA_DIR) / "derived" / name
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key(name, parts)}{suffix}"


def trim(max_bytes=MAX_BYTES):
    """Remove the least recently used entries once the cache is larger than max_bytes."""
    root = Path(settings.DATA_DIR) / "derived"
    if not root.exists():
        return
    files = sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.stat().st_atime)
    total = sum(p.stat().st_size for p in files)
    for p in files:
        if total <= max_bytes:
            break
        total -= p.stat().st_size
        p.unlink(missing_ok=True)
