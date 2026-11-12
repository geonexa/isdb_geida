"""
Population helpers: people per class or band, population-weighted statistics, distance to features
on the run grid.
"""
import numpy as np


def people(pop, mask=None):
    """Total people (NaN = 0) inside mask."""
    a = np.nan_to_num(pop.data if hasattr(pop, "data") else pop, nan=0.0)
    return float(a[mask].sum()) if mask is not None else float(a.sum())


def block_density(cells, res_m, block_m=1000):
    """People per km² of the block_m x block_m block each cell falls in (GHSL density thresholds are for 1 km cells)."""
    k = max(1, int(round(block_m / res_m)))
    rows, cols = cells.shape
    a = np.nan_to_num(cells, nan=0.0)
    pad = np.pad(a, ((0, (-rows) % k), (0, (-cols) % k)))
    sums = pad.reshape(pad.shape[0] // k, k, pad.shape[1] // k, k).sum(axis=(1, 3))
    dens = sums / ((k * res_m) ** 2 / 1e6)
    return np.repeat(np.repeat(dens, k, axis=0), k, axis=1)[:rows, :cols]


def weighted_mean(values, weights, mask):
    """Population-weighted mean of values inside mask (pixels where both are known)."""
    ok = mask & np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    w = weights[ok]
    return float((values[ok] * w).sum() / w.sum()) if w.sum() > 0 else None


def weighted_median(values, weights, mask):
    ok = mask & np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not ok.any():
        return None
    v, w = values[ok], weights[ok]
    order = np.argsort(v)
    cum = np.cumsum(w[order])
    return float(v[order][np.searchsorted(cum, cum[-1] / 2)])


def band_rows(values, weights, mask, edges, labels, px_km2, cumulative=True):
    """People and area per band of values ([edges[i], edges[i+1]) ; last band open), with shares."""
    pop = np.nan_to_num(weights, nan=0.0)
    ok = mask & np.isfinite(values)
    total = float(pop[ok].sum())
    k = np.digitize(values, edges[1:])
    rows, cum = [], 0.0
    for i, label in enumerate(labels):
        sel = ok & (k == i)
        p = float(pop[sel].sum())
        cum += p
        row = {"label": label, "people": round(p), "share": round(100 * p / total, 1) if total else 0,
               "area_km2": round(float(sel.sum()) * px_km2, 1)}
        if cumulative:
            row["cumulative"] = round(100 * cum / total, 1) if total else 0
        rows.append(row)
    return rows


def to_grid_coords(geoms_lonlat, crs):
    """shapely geometries in lon/lat -> the grid CRS (UTM metres)."""
    import shapely
    from rasterio.warp import transform

    def fn(xy):
        if not len(xy):
            return xy
        xs, ys = transform("EPSG:4326", crs, xy[:, 0].tolist(), xy[:, 1].tolist())
        return np.column_stack([xs, ys])
    return shapely.transform(np.asarray(geoms_lonlat, dtype=object), fn)


def distance_to(geoms_grid, grid):
    """Distance in metres from every cell centre to the nearest feature (points, lines or polygons in grid CRS).

    Features are burnt into the grid (all touched cells), then a Euclidean distance transform is run;
    features outside the grid are clamped to its edge so near-edge distances stay sensible.
    Returns None when there are no features.
    """
    import shapely
    from rasterio.features import rasterize
    from scipy.ndimage import distance_transform_edt

    geoms = [g for g in geoms_grid if g is not None and not shapely.is_empty(g)]
    if not geoms:
        return None
    rows, cols = grid.shape
    burnt = rasterize(((g, 1) for g in geoms), out_shape=grid.shape, transform=grid.transform, all_touched=True,
                      fill=0, dtype="uint8")
    if not burnt.any():
        # Every feature is outside the grid: measure from the nearest edge cell towards them instead.
        left, bottom, right, top = grid.bounds
        pts = shapely.get_coordinates(np.array(geoms, dtype=object))
        cx = np.clip(pts[:, 0], left + grid.res / 2, right - grid.res / 2)
        cy = np.clip(pts[:, 1], bottom + grid.res / 2, top - grid.res / 2)
        extra = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
        k = int(np.argmin(extra))
        c, r = ~grid.transform * (cx[k], cy[k])
        burnt[min(int(r), rows - 1), min(int(c), cols - 1)] = 1
        return distance_transform_edt(burnt == 0, sampling=grid.res) + float(extra[k])
    return distance_transform_edt(burnt == 0, sampling=grid.res)


# Population source: WorldPop (yearly 2015–2030, age-sex groups) with GHSL as fallback ---------------------------
GHSL_EPOCHS = list(range(1975, 2031, 5))


def epoch(year):
    """The GHSL epoch nearest to a year."""
    return min(GHSL_EPOCHS, key=lambda e: (abs(e - year), -e))


def population_source(ctx, years, input_name="population"):
    """The dataset id to read population from for these years: the chosen one, or GHSL when WorldPop can't serve them."""
    from ..core.registry import input_dataset
    ds = input_dataset(ctx.manifest, input_name, ctx.params) or "ghsl_pop"
    if ds.startswith("worldpop") and min(years) < 2015:
        if ds != "worldpop":
            from ..core.errors import AnalysisError
            raise AnalysisError("Age and sex groups come from WorldPop, which starts in 2015. Choose 2015 or later.")
        ctx.log(f"WorldPop starts in 2015: GHSL is used for {min(years)}")
        return "ghsl_pop"
    return ds


def read_population(ctx, year, ds, buffer_m=0, input_name="population", bbox=None):
    """
    Population on the run grid from dataset `ds` (worldpop..., ghsl_pop), as (raster, source dict).
    GHSL years are snapped to the nearest 5-year epoch. If WorldPop fails (service down, request limit),
    everyone (not an age group) is read from GHSL instead and the run log says so.
    """
    from ..core.errors import AnalysisError
    from ..data.base import DatasetUnavailable
    from ..data.registry import get_dataset

    def read(dataset, y):
        ctx.params[f"{input_name}_dataset"] = dataset
        return ctx.raster(input_name, year=y, buffer_m=buffer_m, bbox=bbox)

    if ds == "ghsl_pop":
        e = epoch(year)
        if e != year:
            ctx.log(f"GHSL has 5-yearly epochs: {e} is used for {year}")
        return read("ghsl_pop", e), {"dataset": "ghsl_pop", "year": e, "name": "GHSL R2023A", "people": "people", "fallback": False}
    try:
        r = read(ds, year)
        return r, {"dataset": ds, "year": year, "name": "WorldPop R2025A", "people": getattr(get_dataset(ds), "people_label", "people"),
                   "fallback": False}
    except DatasetUnavailable as exc:
        if ds != "worldpop":
            raise AnalysisError(f"{exc}. Age and sex groups need WorldPop; try again later.") from None
        e = epoch(year)
        ctx.log(f"{exc}; using GHSL {e} instead")
        return read("ghsl_pop", e), {"dataset": "ghsl_pop", "year": e, "name": "GHSL R2023A (WorldPop unavailable)",
                                     "people": "people", "fallback": True}
