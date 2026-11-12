"""Schools in the area: OSM schools inside the area, by education level and admin unit (vector)."""
from apps.analysis.ops import inventory

LEVELS = {"0": "Pre-primary", "1": "Primary", "2": "Lower secondary", "3": "Upper secondary",
          "4": "Post-secondary", "5": "Tertiary", "6": "Tertiary", "7": "Tertiary", "8": "Tertiary"}
AMENITY = {"kindergarten": "Pre-primary", "college": "Post-secondary", "university": "Tertiary"}


def level(p):
    """Education level from isced:level, else from the amenity, else 'School (level not mapped)'."""
    raw = str(p.get("isced:level") or "").replace(",", ";")
    found = []
    for x in raw.split(";"):
        x = x.strip()
        lab = LEVELS.get(x[:1]) if x else None
        if lab and lab not in found:
            found.append(lab)
    if found:
        return " + ".join(found)
    return AMENITY.get(p.get("amenity", ""), "School (level not mapped)")


def operator(p):
    return (p.get("operator:type") or "").replace("_", " ").capitalize()


def run(ctx):
    res = inventory.facilities(ctx, "schools", noun="schools", title="Schools", kind_of=level,
                               kind_label="Level", color="#0B3B47",
                               extra=[("operator", "Operator", operator), ("operator_name", "Operator name",
                                                                           lambda p: p.get("operator", ""))])
    snap = ctx.snapshot()
    ctx.summary(inventory.headline(res, "schools and other education facilities", ctx.area_km2, snap)
                + (f"The most common level is {res.kinds[0][0].lower()} ({res.kinds[0][1]}). " if res.kinds else "")
                + "OpenStreetMap coverage varies; confirm against the project's school list.")
    ctx.propose_evidence("9.3", "Educational institutions mapped in the project area (OpenStreetMap)", res.n,
                         "Number", "verify",
                         caveats="Count of existing mapped facilities, not of those built by the project; "
                                 "confirm project-built schools against imagery by date.",
                         reference_date=snap or "current")
    ctx.progress(100)
