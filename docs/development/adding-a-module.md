# Adding an analysis module

This guide walks through creating a new analysis, from folder to evidence. The example
counts markets in the project area.

## 1. Create the folder

```
backend/modules/markets_inventory/
├── manifest.yaml
└── run.py
```

The folder name is the module id. Folders starting with `_` are ignored (use this to park
a module without deleting it).

## 2. Write the manifest

```yaml title="backend/modules/markets_inventory/manifest.yaml"
id: markets_inventory
version: 0.1.0
title: Markets in the area
question: Which markets are mapped in the project area, and in which units?
description: >
  Lists the marketplaces mapped in OpenStreetMap inside the area of influence and
  counts them per administrative unit.
status: experimental             # curated once reviewed
category: social                 # an id from modules/categories.yaml
themes: [livelihoods]
phases: [preparation, implementation, completion]
cri: []                          # e.g. [{code: "9.3", role: verify}]
inputs:
  required:
    - {name: markets, type: vector_point, default: osm_markets, label: Markets}
parameters:
  - {name: zone_level, type: choice, default: 2, label: Summarise by,
     choices: [{value: 1, label: Province / region (level 1)}, {value: 2, label: District (level 2)}]}
outputs:
  - {type: metric, name: count}
  - {type: table, name: by_kind}
  - {type: table, name: per_zone}
  - {type: table, name: list}
  - {type: vector, name: points}
  - {type: file, name: csv}
```

Datasets (`default:`) must exist in `backend/apps/analysis/datasets/registry.py`. Every
OSM theme in `seeds/data/osm_taxonomy.yaml` is available as `osm_<theme>`, and polygon
themes also as `osm_<theme>_points`.

## 3. Write `run.py`

For a facility inventory, the shared helper `apps/analysis/inventory.py` produces the
standard outputs (count, table by type, table per unit, feature list, map layer, CSV):

```python title="backend/modules/markets_inventory/run.py"
"""Markets in the area: OSM marketplaces inside the area, per admin unit (vector)."""
from apps.analysis import inventory


def run(ctx):
    res = inventory.facilities(ctx, "markets", noun="markets", title="Markets",
                               kind_of=lambda p: (p.get("amenity") or "market").replace("_", " ").capitalize(),
                               kind_label="Type", color="#C9A25B")
    ctx.summary(inventory.headline(res, "markets", ctx.area_km2, ctx.snapshot())
                + "OpenStreetMap coverage varies; confirm locally.")
```

To propose evidence for an indicator, add for example:

```python
    ctx.propose_evidence("9.3", "Facilities mapped in the project area (OpenStreetMap)", res.n,
                         "Number", "verify", caveats="Mapped facilities, not project outputs.",
                         reference_date=ctx.snapshot() or "current")
```

The `ctx` object (`apps.analysis.runner.RunContext`) provides:

| Member | Use |
|---|---|
| `ctx.params`, `ctx.area`, `ctx.area_km2`, `ctx.iso3`, `ctx.bbox(buffer_m)` | Inputs and the area |
| `ctx.dataset(name, bbox)`, `ctx.try_dataset(...)` | A raster or file input, downloaded and cached |
| `ctx.features(name, bbox)`, `ctx.try_features(...)` | A vector input as a `vector.Layer` (metres) |
| `ctx.zones(level)`, `ctx.vzones(level)` | Administrative units clipped to the area; `vzones` can `assign`, `count` and `measure` |
| `ctx.snapshot()` | OSM snapshot date(s) used, for summaries and evidence |
| `ctx.log(...)`, `ctx.progress(pct)` | Shown live to the user |
| `ctx.add_metric / add_table / add_image / add_vector / add_file`, `ctx.summary(text)` | Results |
| `ctx.propose_evidence(cri, label, value, unit, role, caveats, reference_date)` | Evidence for matching indicators |
| `raise ModuleError("…")` | A clear failure message for the user |

The full reference, including vector styles, is `backend/modules/README.md`. Look at
`schools_inventory` and `apps/analysis/inventory.py` for a complete example.

## 4. Register and run

```bash
cd backend
python manage.py sync_modules         # or `seed`
```

Open a project → **Analyses**: the module appears under its category with its
availability. Run it and check the outputs.

## 5. Test

Add a test to `backend/apps/analysis/tests.py` that runs the module on the offline
fixture (two administrative units and local GeoJSON layers) and checks that per-unit
numbers add up to the total:

```bash
python manage.py test apps.analysis
```

## 6. Document and release

- Add the module to [Analysis modules](../architecture/analysis-modules.md) and to the
  table in `backend/modules/README.md`.
- Add a [Changelog](../changelog.md) entry.
- Bump `version` in the manifest on every change that alters results; past runs keep the
  version they ran with.
