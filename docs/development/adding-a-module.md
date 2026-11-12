# Adding an analysis module

This guide walks through creating a new analysis, from folder to evidence. The example
counts markets in the project area.

## 1. Create the folder

Scaffold it from the template (`backend/analyses/_template/`):

```bash
cd backend
python manage.py new_analysis infrastructure markets_inventory
```

```
backend/analyses/infrastructure/markets_inventory/
├── manifest.yaml        what it is, phases, inputs, parameters, outputs, limits
├── run.py               def run(ctx): … (the template computes the area per unit)
├── METHOD.md            method, data, outputs, limitations
├── __init__.py
└── tests/
    ├── test_markets_inventory.py   runs the analysis on a test project
    └── fixtures/                   small input files for the tests
```

The folder name is the analysis id (lowercase, unique across categories) and its parent is
the category. If the id is in `analyses/planned.yaml`, the title, question and phases are
filled in from there, and the new analysis replaces the planned entry. Folders starting with
`_` are ignored (use `_parked/` to park an analysis without deleting it).

## 2. Write the manifest

```yaml title="backend/analyses/infrastructure/markets_inventory/manifest.yaml"
id: markets_inventory
version: 0.1.0
title: Markets in the area
question: Which markets are mapped in the project area, and in which units?
description: >
  Lists the marketplaces mapped in OpenStreetMap inside the area of influence and
  counts them per administrative unit.
status: experimental             # curated once reviewed
category: infrastructure         # an id from analyses/categories.yaml
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

Datasets (`default:`) must exist in `backend/apps/analysis/data/registry.py`. Every
OSM theme in `geida_static_data/OSM_Taxonomy/osm_taxonomy.yaml` is available as `osm_<theme>`, and polygon
themes also as `osm_<theme>_points`.

## 3. Write `run.py`

For a facility inventory, the shared helper `apps/analysis/ops/inventory.py` produces the
standard outputs (count, table by type, table per unit, feature list, map layer, CSV):

```python title="backend/analyses/infrastructure/markets_inventory/run.py"
"""Markets in the area: OSM marketplaces inside the area, per admin unit (vector)."""
from apps.analysis.ops import inventory


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

The `ctx` object (`apps.analysis.core.runner.RunContext`) provides:

| Member | Use |
|---|---|
| `ctx.params`, `ctx.area`, `ctx.area_km2`, `ctx.iso3`, `ctx.bbox(buffer_m)` | Inputs and the area |
| `ctx.point(name)` | A `point` parameter (picked on the map in the run form) as `(lon, lat)` |
| `ctx.dataset(name, bbox)`, `ctx.try_dataset(...)` | A raster or file input, downloaded and cached |
| `ctx.features(name, bbox)`, `ctx.try_features(...)` | A vector input as a `vector.Layer` (metres) |
| `ctx.zones(level)`, `ctx.vzones(level)` | Administrative units clipped to the area; `vzones` can `assign`, `count` and `measure` |
| `ctx.snapshot()` | OSM snapshot date(s) used, for summaries and evidence |
| `ctx.log(...)`, `ctx.progress(pct)` | Shown live to the user |
| `ctx.add_metric / add_table / add_image / add_vector / add_file`, `ctx.summary(text)` | Results |
| `ctx.propose_evidence(cri, label, value, unit, role, caveats, reference_date)` | Evidence for matching indicators |
| `raise AnalysisError("…")` | A clear failure message for the user (`from apps.analysis.core.errors import AnalysisError`) |

The full reference, including vector styles, is `backend/analyses/README.md`. Look at
`schools_inventory` and `apps/analysis/ops/inventory.py` for a complete example.

## 4. Check and run

```bash
python manage.py check_analyses              # schema, run(), datasets, legends, METHOD.md, tests
python manage.py document_analyses           # rewrite docs/analyses/ from the manifests and METHOD.md
python manage.py check_analyses --env        # also: GDAL, GRASS, WhiteboxTools on this machine
python manage.py run_analysis markets_inventory --project ABDCSD --param zone_level=1
```

`run_analysis` runs it straight away (no queue), records the run like any other and prints
the outputs. Open the project → **Analyses**: the analysis appears under its category, in
the phases its manifest lists, with its availability. After every run the platform checks
that all outputs the manifest declares were produced (mark one `optional: true` if it
depends on optional data; a family of outputs can be declared as `layer_*`).

## 5. Test

The scaffolded `tests/test_<id>.py` uses `AnalysisTestCase` (`apps.analysis.core.testing`):
a test project with a rectangular area, temporary data and media folders, and helpers to
run the analysis and read its outputs.

```python
from apps.analysis.core.testing import AnalysisTestCase


class TestMarketsInventory(AnalysisTestCase):
    analysis_id = "markets_inventory"

    def test_counts_markets(self):
        self.use_dataset("osm_markets", self.fixture("markets.geojson"))  # tests/fixtures/
        run = self.run_analysis({"zone_level": 2})
        self.assertEqual(self.metric(run, "count"), 3)
```

```bash
python manage.py test analyses.infrastructure.markets_inventory   # this analysis
python manage.py test                                             # everything
```

## 6. Document and release

- Add the module to [Analysis modules](../architecture/analysis-modules.md) and to the
  table in `backend/analyses/README.md`.
- Add a [Changelog](../changelog.md) entry.
- Bump `version` in the manifest on every change that alters results; past runs keep the
  version they ran with.
