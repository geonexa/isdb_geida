"""Health facilities in the area: OSM hospitals, clinics and health posts by type and admin unit."""
from apps.analysis.ops import inventory

TYPES = {"hospital": "Hospital", "clinic": "Clinic / health centre", "centre": "Clinic / health centre",
         "health_post": "Health post", "doctor": "Doctor", "doctors": "Doctor", "birthing_center": "Birthing centre"}


def kind(p):
    for key in ("healthcare", "amenity"):
        if p.get(key) in TYPES:
            return TYPES[p[key]]
    return "Other health facility"


def run(ctx):
    res = inventory.facilities(ctx, "health", noun="health facilities", title="Health facilities", kind_of=kind,
                               color="#B42318",
                               extra=[("level", "Level", lambda p: p.get("healthcare:level", "")),
                                      ("operator", "Operator", lambda p: (p.get("operator:type") or "").capitalize()),
                                      ("beds", "Beds", lambda p: p.get("beds", ""))])
    snap = ctx.snapshot()
    hospitals = dict(res.kinds).get("Hospital", 0)
    ctx.summary(inventory.headline(res, "health facilities", ctx.area_km2, snap)
                + f"{hospitals} {'is a hospital' if hospitals == 1 else 'are hospitals'}. "
                + "OpenStreetMap coverage varies; confirm against the Ministry of Health facility list.")
    ctx.propose_evidence("8.1", "Health facilities mapped in the project area (OpenStreetMap)", res.n, "Number",
                         "verify",
                         caveats="Count of existing mapped facilities, not of those built or equipped by the project; "
                                 "confirm project facilities against imagery by date.",
                         reference_date=snap or "current")
    ctx.progress(100)
