"""School access: people living farther than a threshold distance from the nearest school."""
import json

import numpy as np
from scipy.ndimage import distance_transform_edt

from apps.analysis import raster
from apps.analysis.runner import ModuleError


def run(ctx):
    thr = float(ctx.params["threshold_m"])
    # Look for schools and people a threshold beyond the area, so edge cells see nearby schools.
    bbox = ctx.bbox(buffer_m=thr)
    schools_path = ctx.dataset("schools", bbox)
    schools = json.loads(open(schools_path).read())["features"]
    pop, t, nd = raster.read_tif(ctx.dataset("population", bbox))
    pop = np.where((pop == nd) | ~np.isfinite(pop) | (pop < 0), 0, pop).astype("float64") if nd is not None else np.nan_to_num(pop)
    ctx.progress(35)

    # Points to raster (school cells = 0 distance) --------------------------------------
    seeds = np.ones(pop.shape, dtype=bool)
    inv = ~t
    n_in_grid = 0
    for f in schools:
        x, y = f["geometry"]["coordinates"][:2]
        col, row = inv * (x, y)
        r, c = int(row), int(col)
        if 0 <= r < pop.shape[0] and 0 <= c < pop.shape[1]:
            seeds[r, c] = False
            n_in_grid += 1
    inside = raster.area_mask(ctx.area_geojson, t, pop.shape)
    if not inside.any():
        raise ModuleError("The population grid doesn't cover the project area.")
    lat = (ctx.area.extent[1] + ctx.area.extent[3]) / 2
    dy, dx = raster.pixel_size_m(t, lat)
    if n_in_grid:
        dist = distance_transform_edt(seeds, sampling=(dy, dx))
    else:
        dist = np.full(pop.shape, np.inf)
        ctx.log("No schools found within reach of the area: everyone counts as beyond the threshold.")
    ctx.progress(60)

    beyond = (dist > thr) & inside
    total = float(pop[inside].sum())
    far = float(pop[beyond].sum())
    from django.contrib.gis.geos import Point
    in_area = [f for f in schools if ctx.area.contains(Point(*f["geometry"]["coordinates"][:2], srid=4326))]

    zones = ctx.zones(int(ctx.params.get("zone_level") or 3))
    zr = raster.zone_raster([(g, i) for i, _, _, g in zones], t, pop.shape)
    rows = []
    for i, gid, name, _ in zones:
        m = (zr == i) & inside
        tot = float(pop[m].sum())
        if tot <= 0:
            continue
        f_ = float(pop[m & beyond].sum())
        rows.append({"zone": name, "gid": gid, "population": round(tot), "beyond": round(f_),
                     "share": round(f_ / tot * 100, 1)})
    rows.sort(key=lambda r: -r["share"])
    ctx.progress(80)

    # Outputs -----------------------------------------------------------------------------
    km = thr / 1000
    ctx.add_metric("beyond", f"People beyond {km:g} km", round(far), "people")
    ctx.add_metric("share", "Share of population", round(far / total * 100, 1) if total else 0, "%")
    ctx.add_metric("schools", "Schools in the area (OSM)", len(in_area), "")
    ctx.add_table("per_zone", f"People beyond {km:g} km of a school", [
        {"key": "zone", "label": "Unit"}, {"key": "population", "label": "Population"},
        {"key": "beyond", "label": f"Beyond {km:g} km"}, {"key": "share", "label": "Share", "unit": "%"}], rows)

    cls = np.where(beyond & (pop > 0), 2, np.where(inside & (pop > 0), 1, 0)).astype(np.int16)
    small, step = raster.downsample_for_preview(cls)
    bounds = raster.write_png(ctx.path("beyond.png"), raster.colorize(small, {1: (171, 217, 233), 2: (215, 48, 39)}), t * t.scale(step, step))
    ctx.add_image("beyond_map", f"Population beyond {km:g} km", "beyond.png", bounds,
                  [{"label": f"Within {km:g} km", "color": "#abd9e9"}, {"label": f"Beyond {km:g} km", "color": "#d73027"}])
    ctx.path("schools.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": schools}))
    ctx.add_vector("school_points", "Schools", "schools.geojson", {"color": "#0B3B47"})

    worst = ", ".join(f"{r['zone']} ({r['share']:.0f}%)" for r in rows[:3])
    ctx.summary(
        f"About {far:,.0f} people ({(far / total * 100) if total else 0:.0f}% of {total:,.0f}) live more than {km:g} km "
        f"from the nearest school. The highest shares are in {worst or 'n/a'}. {len(in_area)} schools are mapped in "
        f"the area in OpenStreetMap. Population: WorldPop 2020; schools: OpenStreetMap (completeness varies).")
    ctx.propose_evidence("9.1", f"People living within {km:g} km of a school", round(total - far), "Number", "estimate",
                         caveats="Proxy for reach (distance to the nearest mapped school), not for enrolment or attendance. "
                                 "Population from WorldPop 2020 (modelled); school locations from OpenStreetMap.",
                         reference_date="2020")
    ctx.propose_evidence("9.3", "Schools mapped in the project area (OpenStreetMap)", len(in_area), "Number", "verify",
                         caveats="Count of existing mapped schools; confirm project-built schools against imagery by date.",
                         reference_date="current")
    ctx.progress(100)
