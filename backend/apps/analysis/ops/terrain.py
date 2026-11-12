"""
Terrain from an elevation model on a metric grid (the run grid, UTM): slope, aspect,
hillshade (Horn's method, as gdaldem), classification and contours (GDAL).

All functions take and return ops.grid.Raster; NaN marks no data. Pixels next to no data
(or at the edge) get NaN slope / aspect / hillshade, so read the DEM with a small buffer
(DEM_BUFFER_M) to keep values valid up to the area's border.
"""
import math

import numpy as np

DEM_BUFFER_M = 250   # read DEMs this far beyond the area so edge pixels have neighbours

ASPECT_CLASSES = [  # (label, from°, to°), clockwise from north; flat land is class 0
    ("North", 337.5, 22.5), ("North-east", 22.5, 67.5), ("East", 67.5, 112.5), ("South-east", 112.5, 157.5),
    ("South", 157.5, 202.5), ("South-west", 202.5, 247.5), ("West", 247.5, 292.5), ("North-west", 292.5, 337.5),
]


def _windows(z):
    """The 8 neighbours of every pixel (a b c / d e f / g h i), NaN beyond the edges."""
    p = np.pad(z, 1, mode="constant", constant_values=np.nan)
    return (p[:-2, :-2], p[:-2, 1:-1], p[:-2, 2:], p[1:-1, :-2], p[1:-1, 2:], p[2:, :-2], p[2:, 1:-1], p[2:, 2:])


def gradients(dem):
    """dz/dx (east) and dz/dy (north) in metres per metre, Horn's 3×3 method."""
    a, b, c, d, f, g, h, i = _windows(dem.data.astype("float64"))
    xres, yres = abs(dem.transform.a), abs(dem.transform.e)
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * xres)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * yres)  # rows run southwards: north minus south
    return dzdx, dzdy


def slope(dem, units="degrees"):
    """Slope in degrees (0–90) or percent rise."""
    dzdx, dzdy = gradients(dem)
    rise = np.hypot(dzdx, dzdy)
    data = rise * 100 if units == "percent" else np.degrees(np.arctan(rise))
    return dem.like(data, units=units)


def aspect(dem, flat_degrees=1.0):
    """Direction the slope faces, degrees clockwise from north (0–360); NaN where flatter than flat_degrees."""
    dzdx, dzdy = gradients(dem)
    # The surface faces down-slope: opposite of the gradient (which points up-slope).
    data = (np.degrees(np.arctan2(-dzdx, -dzdy)) + 360) % 360
    flat = np.degrees(np.arctan(np.hypot(dzdx, dzdy))) < flat_degrees
    data = np.where(flat, np.nan, data)
    return dem.like(data)


def aspect_classes(asp, slope_deg=None, flat_degrees=1.0):
    """Aspect as classes 1–8 (ASPECT_CLASSES order) and 0 for flat; NaN where no data."""
    a = asp.data
    out = np.full(a.shape, np.nan, dtype="float32")
    for k, (_, lo, hi) in enumerate(ASPECT_CLASSES, start=1):
        sel = ((a >= lo) | (a < hi)) if lo > hi else ((a >= lo) & (a < hi))
        out[sel & np.isfinite(a)] = k
    if slope_deg is not None:
        out[np.isfinite(slope_deg.data) & (slope_deg.data < flat_degrees)] = 0
    return asp.like(out)


def hillshade(dem, azimuth=315.0, altitude=45.0, z_factor=1.0):
    """Shaded relief 0 (shadow) – 255 (lit), sun from azimuth (° from north) at altitude (° above horizon)."""
    dzdx, dzdy = gradients(dem)
    dzdx, dzdy = dzdx * z_factor, dzdy * z_factor
    zen, az = math.radians(90 - altitude), math.radians(azimuth)
    sl = np.arctan(np.hypot(dzdx, dzdy))
    asp = np.arctan2(-dzdx, -dzdy)  # facing direction, clockwise from north
    shade = np.cos(zen) * np.cos(sl) + np.sin(zen) * np.sin(sl) * np.cos(az - asp)
    return dem.like(np.clip(shade, 0, 1) * 255)


def classify(r, breaks):
    """Classes 1..len(breaks)+1 for values split at breaks (ascending); NaN stays NaN."""
    data = r.data
    out = np.digitize(np.where(np.isfinite(data), data, 0), breaks).astype("float32") + 1
    out[~np.isfinite(data)] = np.nan
    return r.like(out)


def class_areas(classes, labels, mask=None):
    """[{class, label, area_km2, share}] for classes 1..len(labels) (and 0 when labels has key 0)."""
    sel = np.isfinite(classes.data) if mask is None else np.isfinite(classes.data) & mask
    px_km2 = classes.grid.pixel_area_m2 / 1e6
    vals = classes.data[sel].astype(int)
    total = max(vals.size, 1)
    rows = []
    for k, label in labels.items():
        n = int((vals == k).sum())
        rows.append({"class": k, "label": label, "area_km2": round(n * px_km2, 1), "share": round(100 * n / total, 1)})
    return rows


def nice_interval(lo, hi, lines=15):
    """A round contour interval giving about `lines` contours between lo and hi."""
    span = max(hi - lo, 1.0)
    raw = span / lines
    mag = 10 ** math.floor(math.log10(raw))
    for s in (1, 2, 2.5, 5, 10):
        if s * mag >= raw:
            return s * mag
    return 10 * mag


def smooth(r, size=3):
    """Mean filter (size × size) ignoring NaN: removes pixel noise before contouring."""
    from scipy.ndimage import uniform_filter
    valid = np.isfinite(r.data)
    filled = np.where(valid, r.data, 0).astype("float64")
    num = uniform_filter(filled, size=size, mode="nearest")
    den = uniform_filter(valid.astype("float64"), size=size, mode="nearest")
    out = np.where(valid & (den > 0), num / np.maximum(den, 1e-9), np.nan)
    return r.like(out)


def contours(r, interval, gpkg_path, geojson_path, index_every=5, simplify_m=None, base=0.0):
    """
    Contour lines of r every `interval` (starting from base), written as a GeoPackage in the
    raster's CRS (download) and a simplified GeoJSON in lon/lat (map). Each line has `elev` and
    `index` (1 for every index_every-th contour, drawn bolder). Returns (lines, total_km).
    """
    from osgeo import gdal, ogr, osr

    gdal.UseExceptions()
    rows, cols = r.data.shape
    nodata = -32768.0
    src = gdal.GetDriverByName("MEM").Create("", cols, rows, 1, gdal.GDT_Float32)
    t = r.transform
    src.SetGeoTransform((t.c, t.a, t.b, t.f, t.d, t.e))
    srs = osr.SpatialReference()
    srs.SetFromUserInput(r.crs)
    src.SetProjection(srs.ExportToWkt())
    band = src.GetRasterBand(1)
    band.SetNoDataValue(nodata)
    band.WriteArray(np.where(np.isfinite(r.data), r.data, nodata).astype("float32"))

    mem = ogr.GetDriverByName("Memory").CreateDataSource("contours")
    layer = mem.CreateLayer("contours", srs, ogr.wkbLineString)
    layer.CreateField(ogr.FieldDefn("id", ogr.OFTInteger))
    layer.CreateField(ogr.FieldDefn("elev", ogr.OFTReal))
    gdal.ContourGenerate(band, float(interval), float(base), [], 1, nodata, layer, 0, 1)

    layer.CreateField(ogr.FieldDefn("index", ogr.OFTInteger))
    lines, total_m = 0, 0.0
    step = interval * index_every
    layer.ResetReading()
    for feat in layer:
        elev = feat.GetField("elev")
        feat.SetField("index", 1 if abs((elev - base) / step - round((elev - base) / step)) < 1e-6 else 0)
        layer.SetFeature(feat)
        lines += 1
        total_m += feat.GetGeometryRef().Length()

    gdal.VectorTranslate(str(gpkg_path), mem, format="GPKG", layerName="contours")
    opts = {"format": "GeoJSON", "dstSRS": "EPSG:4326", "layerCreationOptions": ["COORDINATE_PRECISION=6"]}
    if simplify_m:
        opts["simplifyTolerance"] = simplify_m
    gdal.VectorTranslate(str(geojson_path), mem, **opts)
    return lines, total_m / 1000
