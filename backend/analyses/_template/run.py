"""{{title}}: {{question}}

Replace the body with the analysis. Keep it short: get inputs from ctx, compute with the
toolkit (apps.analysis.ops, apps.analysis.render), add outputs, write a one-line summary.
Raise AnalysisError for a failure the user should read.
"""
from apps.analysis.core.errors import AnalysisError  # noqa: F401 (use for user-facing failures)


def run(ctx):
    zones = ctx.vzones(int(ctx.params.get("zone_level") or 2))
    ctx.progress(50)
    rows = [{"unit": name, "area_km2": round(km2, 1)} for _, _, name, km2 in zones.rows()]
    total = sum(r["area_km2"] for r in rows)

    ctx.add_metric("area_km2", "Area analysed", round(total, 1), "km²")
    ctx.add_table("per_zone", "Area per administrative unit",
                  [{"key": "unit", "label": "Unit"}, {"key": "area_km2", "label": "Area", "unit": "km²"}], rows)
    ctx.summary(f"The area of influence covers {total:,.0f} km² in {len(rows)} unit(s).")
