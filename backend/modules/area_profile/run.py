"""Area profile: what OpenStreetMap holds for the area, layer by layer, per admin unit (vector).

The layers are the manifest's inputs; adding one there adds a row here.
"""

import numpy as np

from apps.analysis import inventory, vector
from apps.analysis.osm import taxonomy
from apps.analysis.registry import read_categories

MAX_ON_MAP = 60_000  # features per layer drawn on the map; above this the layer is listed but not drawn
DRAW_ORDER = {"vector_polygon": 0, "vector_line": 1, "vector_point": 2}  # polygons under lines under points
PLACE_ORDER = ["city", "town", "suburb", "village", "quarter", "neighbourhood", "hamlet", "locality", "isolated_dwelling"]


def _inputs(manifest):
    for group in ("required", "optional"):
        yield from manifest.get("inputs", {}).get(group, []) or []


def _layer_meta(dataset_id):
    """(taxonomy layer, category id) for osm_<layer>[_points]."""
    lid = dataset_id.removeprefix("osm_").removesuffix("_points")
    try:
        lay = taxonomy.get_layer(lid)
        return lay, lay.category
    except KeyError:
        return None, ""


def run(ctx):
    level = int(ctx.params.get("zone_level") or 2)
    zones = ctx.vzones(level)
    bbox = ctx.bbox(buffer_m=100)
    cat_title = {c["id"]: c["title"] for c in read_categories()}
    area = ctx.area_km2 or 0

    rows, zone_vals, columns, missing, maps = [], {int(i): {} for i in zones.ids}, [], [], []
    places = None
    inputs = list(_inputs(ctx.manifest))
    for k, inp in enumerate(inputs):
        name, kind = inp["name"], inp.get("type", "")
        layer = ctx.try_features(name, bbox)
        ctx.progress(5 + 75 * (k + 1) / len(inputs))
        if layer is None:
            missing.append(inp.get("label") or name)
            continue
        _, cat = _layer_meta(inp.get("default", ""))
        label = inp.get("label") or name
        if kind == "vector_line":
            m = zones.measure(layer.geoms)
            per = {z: d.get(None, 0.0) for z, d in m.items()}
            value, unit, digits = sum(per.values()), "km", 1
        elif kind == "vector_polygon":
            m = zones.measure(layer.geoms)
            per = {z: d.get(None, 0.0) for z, d in m.items()}
            value, unit, digits = sum(per.values()), "km²", 2
        else:
            z = zones.assign(layer.geoms)
            counts = zones.count(z)
            per = {int(i): int(counts[i]) for i in zones.ids}
            value, unit, digits = sum(per.values()), "", 0
            if name == "places":
                places = (layer.subset(z > 0), z[z > 0])
        if name != "places" and inp.get("color"):
            maps.append((DRAW_ORDER.get(kind, 2), k, inp, label, layer, kind))
        rows.append({"category": cat_title.get(cat, cat.replace("_", " ").capitalize()), "layer": label,
                     "value": round(value, digits) if digits else int(value), "unit": unit or "features",
                     "per_100km2": round(value / area * 100, 2) if area else 0})
        key = f"l{k}"
        columns.append({"key": key, "label": label, **({"unit": unit} if unit else {})})
        for z, v in per.items():
            zone_vals[z][key] = round(v, digits) if digits else int(v)
        ctx.log(f"{label}: {value:,.{digits}f} {unit or 'features'}")

    order = {c["title"]: c["order"] for c in read_categories()}
    rows.sort(key=lambda r: (order.get(r["category"], 99), r["category"]))

    per_zone = [{"zone": name, "gid": gid, "area_km2": round(a, 1), **zone_vals[int(i)]} for i, gid, name, a in zones.rows()]
    per_zone.sort(key=lambda r: r["zone"])

    # One map layer per category, each in its manifest colour --------------------------------
    names = dict(zip(zones.ids.tolist(), zones.names))
    for _, k, inp, label, layer, kind in sorted(maps, key=lambda m: (m[0], m[1])):
        if kind == "vector_point":
            z = zones.assign(layer.geoms)
            idx = np.flatnonzero(z > 0)
            geoms = layer.geoms[idx]
            props = [vector.osm_props(layer.props[j], zone=names[int(z[j])]) for j in idx.tolist()]
        else:
            idx, geoms = vector.clip(layer.geoms, zones.union)
            props = [vector.osm_props(layer.props[j]) for j in idx.tolist()]
        if not len(geoms):
            continue
        if len(geoms) > MAX_ON_MAP:
            ctx.log(f"{label}: {len(geoms):,} features, too many to draw; counted in the tables only.")
            continue
        fname = f"layer_{inp['name']}.geojson"
        vector.write_geojson(ctx.path(fname), ctx.frame, geoms, props)
        style = {"color": inp["color"], "opacity": 0.55,
                 "shape": {"vector_point": "point", "vector_line": "line"}.get(kind, "polygon")}
        if kind == "vector_point":
            style["radius"] = float(inp.get("radius", 4))
        elif kind == "vector_line":
            style["width"] = float(inp.get("width", 1.4))
        ctx.add_vector(f"layer_{inp['name']}", label, fname, style)

    # Named places ---------------------------------------------------------------------
    place_rows = []
    if places is not None and len(places[0]):
        lay, zz = places
        lon, lat = vector.lonlat(ctx.frame, lay.geoms)
        names = dict(zip(zones.ids.tolist(), zones.names))
        for j, p in enumerate(lay.props):
            place_rows.append({"name": p.get("name") or "(unnamed)", "type": (p.get("place") or "").replace("_", " "),
                               "population": p.get("population", ""), "zone": names[int(zz[j])],
                               "lon": round(float(lon[j]), 5), "lat": round(float(lat[j]), 5), "osm_id": p.get("osm_id", "")})
        rank = {t.replace("_", " "): i for i, t in enumerate(PLACE_ORDER)}
        place_rows.sort(key=lambda r: (rank.get(r["type"], 99), r["name"]))
        vector.write_geojson(ctx.path("places.geojson"), ctx.frame, lay.geoms,
                             [vector.osm_props(p, zone=names[int(zz[j])]) for j, p in enumerate(lay.props)])
        ctx.add_vector("places_map", "Named places", "places.geojson", {
            "property": "place", "color": "#495057", "radius": 3,
            "classes": [{"value": "city", "color": "#0B3B47", "label": "City", "radius": 7},
                        {"value": "town", "color": "#0B3B47", "label": "Town", "radius": 5.5},
                        {"value": "village", "color": "#1C7C8C", "label": "Village", "radius": 4},
                        {"value": "hamlet", "color": "#6CA6B0", "label": "Hamlet", "radius": 3}]})

    # Outputs --------------------------------------------------------------------------
    get = {r["layer"]: r["value"] for r in rows}
    labels = {i["name"]: i.get("label") or i["name"] for i in inputs}
    for name, metric, title, unit in [("buildings", "buildings", "Buildings", ""), ("roads", "roads_km", "Roads", "km"),
                                      ("schools", "schools", "Schools", ""), ("health", "health", "Health facilities", ""),
                                      ("water_points", "water_points", "Water points", "")]:
        if labels.get(name) in get:
            ctx.add_metric(metric, title, get[labels[name]], unit)
    ctx.add_metric("places", "Named places", len(place_rows), "")
    ctx.add_table("inventory", "What is mapped in the area", [
        {"key": "category", "label": "Category"}, {"key": "layer", "label": "Layer"},
        {"key": "value", "label": "Mapped"}, {"key": "unit", "label": "Unit"}, {"key": "per_100km2", "label": "Per 100 km²"}],
        rows, note=inventory.OSM_CAVEAT)
    ctx.add_table("per_zone", "By administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"}, *columns], per_zone)
    ctx.add_table("place_list", "Named places", [
        {"key": "name", "label": "Name"}, {"key": "type", "label": "Type"}, {"key": "population", "label": "Population (OSM)"},
        {"key": "zone", "label": "Unit"}, {"key": "lon", "label": "Lon"}, {"key": "lat", "label": "Lat"},
        {"key": "osm_id", "label": "OSM"}], place_rows)
    vector.write_csv(ctx.path("inventory.csv"), rows)
    ctx.add_file("csv", "Inventory (CSV)", ctx.path("inventory.csv"))

    snap = ctx.snapshot()
    by_type = {}
    for r in place_rows:
        by_type[r["type"]] = by_type.get(r["type"], 0) + 1
    settle = ", ".join(f"{c} {t}{'s' if c > 1 else ''}" for t, c in sorted(by_type.items(), key=lambda kv: -kv[1])[:3])
    ctx.summary(
        f"OpenStreetMap{f' (snapshot {snap})' if snap else ''} holds the following for the {area:,.0f} km² area: "
        + "; ".join(f"{r['layer'].lower()} {r['value']:,}{(' ' + r['unit']) if r['unit'] != 'features' else ''}"
                    for r in rows if r["value"]) + ". "
        + (f"Named places: {settle}. " if settle else "")
        + (f"Not available: {', '.join(missing)}. " if missing else "")
        + "Counts are of mapped features; completeness varies, especially for buildings in rural areas.")
    ctx.progress(100)
