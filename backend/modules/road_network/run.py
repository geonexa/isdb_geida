"""Road network: km of OSM road by class and surface, bridges and density per admin unit (vector)."""
import shapely

from apps.analysis import inventory, vector

# (class, label, colour, line width, highway values)
CLASSES = [
    ("trunk", "Motorway / trunk", "#B42318", 3.2, {"motorway", "trunk", "motorway_link", "trunk_link"}),
    ("primary", "Primary", "#E8590C", 2.6, {"primary", "primary_link"}),
    ("secondary", "Secondary", "#F59F00", 2.2, {"secondary", "secondary_link"}),
    ("tertiary", "Tertiary", "#0B7285", 1.8, {"tertiary", "tertiary_link"}),
    ("local", "Local / residential", "#495057", 1.2, {"unclassified", "residential", "living_street", "road"}),
    ("service", "Service", "#868E96", 0.9, {"service"}),
    ("track", "Track", "#A47148", 0.9, {"track"}),
]
CLASS_OF = {v: c for c, _, _, _, vs in CLASSES for v in vs}
LABEL = {c: lab for c, lab, *_ in CLASSES}
MAJOR = {"trunk", "primary", "secondary", "tertiary"}
PAVED = {"paved", "asphalt", "concrete", "concrete:plates", "concrete:lanes", "paving_stones", "sett", "chipseal",
         "cobblestone", "metal", "bricks", "unhewn_cobblestone"}
UNPAVED = {"unpaved", "gravel", "dirt", "earth", "ground", "compacted", "sand", "mud", "fine_gravel", "grass",
           "laterite", "pebblestone", "rock", "woodchips", "salt", "murram"}


def surface(p):
    s = (p.get("surface") or "").strip().lower()
    return "paved" if s in PAVED else "unpaved" if s in UNPAVED else "unknown"


def run(ctx):
    layer = ctx.features("roads", ctx.bbox(buffer_m=100))
    ctx.progress(35)
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    cls = [CLASS_OF.get(p.get("highway", ""), "local") for p in layer.props]
    srf = [surface(p) for p in layer.props]
    bridge = [str(p.get("bridge", "")).lower() not in ("", "no") for p in layer.props]

    # One pass: length per unit by "class|surface", then sum the way each table needs.
    by_zone = zones.measure(layer.geoms, [f"{c}|{x}" for c, x in zip(cls, srf)])
    by_zone_bridge = zones.measure(layer.geoms, ["bridge" if b else "" for b in bridge])
    ctx.progress(65)

    def km_of(zone=None, cls_in=None, surface_is=None):
        out = 0.0
        for z, d in by_zone.items():
            if zone is not None and z != zone:
                continue
            for key, v in d.items():
                c, x = key.split("|")
                if (cls_in is None or c in cls_in) and (surface_is is None or x == surface_is):
                    out += v
        return out

    km = km_of()
    major_km = km_of(cls_in=MAJOR)
    paved_km, unpaved_km = km_of(surface_is="paved"), km_of(surface_is="unpaved")
    bridge_km = sum(d.get("bridge", 0.0) for d in by_zone_bridge.values())

    by_class = []
    for c, lab, *_ in CLASSES:
        k = km_of(cls_in={c})
        if k > 0:
            p, u = km_of(cls_in={c}, surface_is="paved"), km_of(cls_in={c}, surface_is="unpaved")
            by_class.append({"class": lab, "km": round(k, 2), "share": round(k / km * 100, 1) if km else 0,
                             "paved_km": round(p, 2), "unpaved_km": round(u, 2), "unknown_km": round(max(k - p - u, 0), 2)})

    per_zone = []
    for i, gid, name, area in zones.rows():
        zk = km_of(zone=i)
        per_zone.append({"zone": name, "gid": gid, "area_km2": round(area, 1), "km": round(zk, 2),
                         "major_km": round(km_of(zone=i, cls_in=MAJOR), 2),
                         "paved_km": round(km_of(zone=i, surface_is="paved"), 2),
                         "density": round(zk / area, 3) if area else 0})
    per_zone.sort(key=lambda r: (-r["km"], r["zone"]))
    ctx.progress(80)

    # Map: roads clipped to the area -------------------------------------------------------
    idx, clipped = vector.clip(layer.geoms, zones.union)
    props = [vector.osm_props(layer.props[j], **{"class": LABEL[cls[j]], "surface_class": srf[j],
                                                  "km_in_area": round(float(shapely.length(g)) / 1e3, 3)})
             for j, g in zip(idx.tolist(), clipped)]
    vector.write_geojson(ctx.path("roads.geojson"), ctx.frame, clipped, props)
    vector.write_csv(ctx.path("roads.csv"), sorted(props, key=lambda r: (r["class"], r.get("name", ""))),
                     ["name", "ref", "highway", "class", "surface", "surface_class", "bridge", "km_in_area", "osm_id"])
    ctx.log(f"{len(layer):,} road segments in the search box, {len(idx):,} inside the area")

    area = ctx.area_km2 or 0
    ctx.add_metric("km", "Road length mapped", round(km, 1), "km")
    ctx.add_metric("major_km", "Primary to tertiary (incl. trunk)", round(major_km, 1), "km")
    ctx.add_metric("density", "Road density", round(km / area, 3) if area else 0, "km/km²")
    ctx.add_metric("paved_share", "Paved (where surface is mapped)",
                   round(paved_km / (paved_km + unpaved_km) * 100) if paved_km + unpaved_km else 0, "%")
    ctx.add_metric("bridges", "On bridges", round(bridge_km, 2), "km")
    ctx.add_table("by_class", "Road length by class", [
        {"key": "class", "label": "Class"}, {"key": "km", "label": "Length", "unit": "km"},
        {"key": "share", "label": "Share", "unit": "%"}, {"key": "paved_km", "label": "Paved", "unit": "km"},
        {"key": "unpaved_km", "label": "Unpaved", "unit": "km"}, {"key": "unknown_km", "label": "Surface not mapped", "unit": "km"}],
        by_class)
    ctx.add_table("per_zone", "Roads by administrative unit", [
        {"key": "zone", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"},
        {"key": "km", "label": "Roads", "unit": "km"}, {"key": "major_km", "label": "Primary–tertiary", "unit": "km"},
        {"key": "paved_km", "label": "Paved", "unit": "km"}, {"key": "density", "label": "Density", "unit": "km/km²"}],
        per_zone, note=inventory.OSM_CAVEAT)
    ctx.add_vector("roads", "Roads by class", "roads.geojson", {
        "property": "class", "color": "#495057", "width": 1.2,
        "classes": [{"value": lab, "color": col, "label": lab, "width": w} for c, lab, col, w, _ in CLASSES]})
    ctx.add_file("csv", "Road segments (CSV)", ctx.path("roads.csv"))

    snap = ctx.snapshot()
    known = paved_km + unpaved_km
    ctx.summary(
        f"{km:,.1f} km of road are mapped in OpenStreetMap inside the {area:,.0f} km² area "
        f"({km / area if area else 0:.2f} km per km²), of which {major_km:,.1f} km are trunk to tertiary roads. "
        + (f"Where the surface is mapped ({known / km * 100 if km else 0:.0f}% of the length), "
           f"{paved_km / known * 100:.0f}% is paved. " if known else "Road surfaces are not mapped here. ")
        + (f"Densest network: {per_zone[0]['zone']} ({per_zone[0]['density']:.2f} km/km²). " if per_zone and km else "")
        + (f"OSM snapshot {snap}. " if snap else "")
        + "Lengths are of the mapped network, clipped to the area.")
    ctx.propose_evidence("2.2", "Primary to tertiary roads mapped in the project area (OpenStreetMap)",
                         round(major_km, 1), "km", "verify",
                         caveats="Length of the existing mapped network, not of roads built or upgraded by the project; "
                                 "use it to check the alignment and verify works against imagery by date.",
                         reference_date=snap or "current")
    ctx.progress(100)
