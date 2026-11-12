"""
Geofabrik OSM extracts: find the smallest region covering an area, download it once,
and keep it in DATA_DIR/osm/<region id>.osm.pbf.

Region choice follows Aleph (alephgeo/osm.py: Source.region / covers; MIT,
© 2026 Belluxx): regions are tried smallest first and the first whose outline
contains the whole box wins, so a project in Kampala gets the Uganda extract,
not Africa. GEOS does the containment test here.

Unlike Aleph, continents are never used: an area whose box crosses a border
(a district plus a buffer, common for IsDB projects) gets the country holding the
box centre, flagged partial, rather than a multi-GB continent download.
"""
import json
import time
import urllib.request
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, Point, Polygon

from .pbf_header import snapshot_time

INDEX_URL = "https://download.geofabrik.de/index-v1.json"
USER_AGENT = "GEIDA/1.0 (IsDB geoinformatics platform)"
INDEX_MAX_AGE = 30 * 24 * 3600  # re-read the region index monthly
# Large countries run to a few GB; anything bigger is refused rather than filling the disk.
MAX_EXTRACT_BYTES = 2 * 1024 ** 3


class GeofabrikUnavailable(Exception):
    """No extract can be used for this area (offline, no covering region, too large)."""


def osm_dir():
    d = Path(settings.DATA_DIR) / "osm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout)


def load_index(refresh=False):
    """Geofabrik's region index (GeoJSON), cached for a month."""
    path = osm_dir() / "geofabrik-index.json"
    fresh = path.exists() and time.time() - path.stat().st_mtime < INDEX_MAX_AGE
    if refresh or not fresh:
        try:
            with _get(INDEX_URL) as r:
                data = r.read()
            json.loads(data)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        except Exception as exc:  # offline: an old index still works
            if not path.exists():
                raise GeofabrikUnavailable(f"Can't read the Geofabrik index: {exc}") from exc
    return json.loads(path.read_text())


def find_region(bbox, index=None):
    """Smallest country-or-smaller Geofabrik region for bbox (w, s, e, n): {id, name, url, partial}.

    A region containing the whole box wins; otherwise the region containing the box
    centre, with partial=True (features across the border are not included).
    Continents (regions without a parent) are never chosen.
    """
    index = index or load_index()
    box = Polygon.from_bbox(bbox)
    centre = Point((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
    candidates = []
    for f in index.get("features", []):
        props = f.get("properties", {})
        url = props.get("urls", {}).get("pbf")
        if not url or not f.get("geometry") or not props.get("parent"):
            continue
        geom = GEOSGeometry(json.dumps(f["geometry"]), srid=4326)
        w, s, e, n = geom.extent
        if w <= centre.x <= e and s <= centre.y <= n:
            candidates.append((geom.area, props, geom))
    candidates.sort(key=lambda c: c[0])
    pick = lambda props, partial: {"id": props["id"], "name": props.get("name", props["id"]),  # noqa: E731
                                   "url": props["urls"]["pbf"], "partial": partial}
    for _, props, geom in candidates:
        if geom.contains(box):
            return pick(props, False)
    for _, props, geom in candidates:
        if geom.contains(centre):
            return pick(props, True)
    raise GeofabrikUnavailable("No Geofabrik country extract covers this area.")


def extract_path(region):
    return osm_dir() / f"{region['id'].replace('/', '_')}.osm.pbf"


def ensure_extract(region, log=print, refresh=False):
    """Local path of the region's .osm.pbf, downloading it the first time (or on refresh)."""
    path = extract_path(region)
    if path.exists() and not refresh:
        return path
    try:
        with _get(region["url"], timeout=120) as r:
            total = int(r.headers.get("Content-Length") or 0)
            if total > MAX_EXTRACT_BYTES:
                raise GeofabrikUnavailable(
                    f"The {region['name']} extract is {total / 1024 ** 3:.0f} GB; too large to download.")
            log(f"OpenStreetMap: downloading the {region['name']} extract from Geofabrik"
                + (f" ({total / 1024 ** 2:,.0f} MB)" if total else ""))
            tmp = path.with_suffix(".part")
            done, step, next_report = 0, 1024 * 1024, 0.25
            with open(tmp, "wb") as out:
                while chunk := r.read(step):
                    out.write(chunk)
                    done += len(chunk)
                    if total and done / total >= next_report:
                        log(f"OpenStreetMap: {done / total:.0%} downloaded")
                        next_report += 0.25
        tmp.replace(path)
    except GeofabrikUnavailable:
        raise
    except Exception as exc:
        raise GeofabrikUnavailable(f"Downloading the {region['name']} extract failed: {exc}") from exc
    return path


def snapshot(path):
    """Snapshot date of an extract as 'YYYY-MM-DD' (from the PBF header, else the file time)."""
    try:
        t = snapshot_time(path)
    except (OSError, ValueError):
        t = None
    if t is None:
        t = time.gmtime(Path(path).stat().st_mtime)
        return time.strftime("%Y-%m-%d", t)
    return t.strftime("%Y-%m-%d")
