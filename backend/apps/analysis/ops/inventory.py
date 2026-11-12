"""
Shared steps for OSM inventory modules (schools, health, community facilities, utilities):
read a taxonomy layer, keep features inside the area, assign admin units, count by
type, and write the standard outputs (headline, per-unit table, type table, feature
list, map layer, CSV). Modules add their own summary and evidence on top.

    res = inventory.facilities(ctx, "schools", noun="schools", kind_of=school_level, color="#0B3B47")
"""
from dataclasses import dataclass

import numpy as np

from . import vector

OSM_CAVEAT = ("OpenStreetMap; completeness varies by country. Counts are of mapped features: "
              "check them against the project's own lists and recent imagery.")


@dataclass
class Inventory:
    n: int
    kinds: list        # [(kind, count)] most common first
    per_zone: list     # table rows
    listing: list      # table rows
    zones_without: list
    layer: vector.Layer
    zone_of: np.ndarray


def facilities(ctx, input_name, *, noun, title, kind_of, kind_label="Type", color="#0B3B47",
               extra=(), zone_level=None, radius=4):
    """Count point features by type and admin unit and add the standard outputs.

    kind_of(props) -> str: the type shown in tables ("Primary", "Clinic", ...).
    extra: [(key, label, fn(props))] additional columns for the feature list.
    """
    level = int(zone_level or ctx.params.get("zone_level") or 3)
    layer = ctx.features(input_name, ctx.bbox(buffer_m=100))
    ctx.progress(40)
    zones = ctx.vzones(level)
    z = zones.assign(layer.geoms)
    inside = layer.subset(z > 0)
    z = z[z > 0]
    n = len(inside)
    ctx.log(f"{len(layer):,} {noun} in the search box, {n:,} inside the area")
    ctx.progress(60)

    kinds = [kind_of(p) or "Other" for p in inside.props]
    kind_counts = sorted(_count(kinds).items(), key=lambda kv: (-kv[1], kv[0]))
    top = [k for k, _ in kind_counts[:4]]
    names = dict(zip(zones.ids.tolist(), zones.names))

    per_zone = []
    for i, gid, name, area in zones.rows():
        here = [k for k, zz in zip(kinds, z) if zz == i]
        row = {"zone": name, "gid": gid, "area_km2": round(area, 1), "count": len(here),
               "per_100km2": round(len(here) / area * 100, 2) if area else 0}
        for j, k in enumerate(top):
            row[f"k{j}"] = sum(1 for x in here if x == k)
        per_zone.append(row)
    per_zone.sort(key=lambda r: (-r["count"], r["zone"]))

    lon, lat = vector.lonlat(ctx.frame, inside.geoms)
    listing = []
    for idx, p in enumerate(inside.props):
        row = {"name": p.get("name") or "(unnamed)", "kind": kinds[idx]}
        for key, _, fn in extra:
            row[key] = fn(p)
        row.update({"zone": names[int(z[idx])], "lon": round(float(lon[idx]), 5), "lat": round(float(lat[idx]), 5),
                    "osm_id": p.get("osm_id", "")})
        listing.append(row)
    listing.sort(key=lambda r: (r["zone"], r["kind"], r["name"]))
    named = sum(1 for r in listing if r["name"] != "(unnamed)")
    zones_without = [r["zone"] for r in per_zone if r["count"] == 0]
    ctx.progress(80)

    # Outputs ---------------------------------------------------------------------------
    area = ctx.area_km2 or 0
    ctx.add_metric("count", f"{title} mapped in the area", n, "")
    ctx.add_metric("density", f"{title} per 100 km²", round(n / area * 100, 2) if area else 0, "")
    ctx.add_metric("named", "With a name", round(named / n * 100) if n else 0, "%")
    ctx.add_metric("zones_without", f"Units with no {noun}", len(zones_without), "")
    ctx.add_table("by_kind", f"{title} by {kind_label.lower()}", [
        {"key": "kind", "label": kind_label}, {"key": "count", "label": "Mapped"}, {"key": "share", "label": "Share", "unit": "%"}],
        [{"kind": k, "count": c, "share": round(c / n * 100, 1)} for k, c in kind_counts])
    ctx.add_table("per_zone", f"{title} by administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "count", "label": title}, {"key": "per_100km2", "label": "Per 100 km²"},
        *[{"key": f"k{j}", "label": k} for j, k in enumerate(top)]], per_zone)
    ctx.add_table("list", f"{title} list", [
        {"key": "name", "label": "Name"}, {"key": "kind", "label": kind_label},
        *[{"key": key, "label": label} for key, label, _ in extra],
        {"key": "zone", "label": "Unit"}, {"key": "lon", "label": "Lon"}, {"key": "lat", "label": "Lat"},
        {"key": "osm_id", "label": "OSM"}], listing, note=OSM_CAVEAT)

    vector.write_geojson(ctx.path(f"{input_name}.geojson"), ctx.frame, inside.geoms,
                         [vector.osm_props(p, kind=k, zone=names[int(zz)])
                          for k, zz, p in zip(kinds, z, inside.props)])
    ctx.add_vector("points", title, f"{input_name}.geojson", {"color": color, "radius": radius})
    vector.write_csv(ctx.path(f"{input_name}.csv"), listing)
    ctx.add_file("csv", f"{title} list (CSV)", ctx.path(f"{input_name}.csv"))
    ctx.progress(90)
    return Inventory(n, kind_counts, per_zone, listing, zones_without, inside, z)


def headline(res, noun, area_km2, snapshot=""):
    """A standard first sentence for inventory summaries."""
    density = res.n / area_km2 * 100 if area_km2 else 0
    text = (f"{res.n:,} {noun} are mapped in OpenStreetMap inside the {area_km2:,.0f} km² area "
            f"({density:.1f} per 100 km²). ")
    if res.n:
        top = res.per_zone[0]
        text += f"Most are in {top['zone']} ({top['count']}). "
    if res.zones_without:
        shown = ", ".join(res.zones_without[:5]) + ("…" if len(res.zones_without) > 5 else "")
        text += f"{len(res.zones_without)} unit(s) have none mapped: {shown}. "
    if snapshot:
        text += f"OSM snapshot {snapshot}. "
    return text


def _count(items):
    out = {}
    for x in items:
        out[x] = out.get(x, 0) + 1
    return out

