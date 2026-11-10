"""Prepare GADM 4.1 admin boundaries (levels 0-3) for the GEIDA platform.

Reads the GADM "levels" GeoPackage (layers ADM_0 ... ADM_5), keeps levels 0-3
for every country, cleans the attributes to one schema, repairs geometries and
writes two GeoPackages:

  gadm41_adm0-3.gpkg             full resolution  (analysis, clipping, area)
  gadm41_adm0-3_simplified.gpkg  simplified, shared edges kept (map display, picker)

Each has layers adm0, adm1, adm2, adm3 with the columns:
  gid, level, iso3, country, name, name_local, type, parent_gid,
  name_1, name_2, name_3, hasc, disputed, area_km2, geometry (MultiPolygon, EPSG:4326)

Usage:
  python prepare_gadm.py <gadm_410-levels.gpkg> <output_dir>   (GEIDA uses backend/data/boundaries) [--countries PAK,UGA | --isdb]
                         [--resume] [--max-seconds 140]

GADM data licence: free for academic and other non-commercial use; redistribution
or commercial use needs permission from GADM (https://gadm.org/license.html).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
import shapely
from pyproj import Geod

# The 57 IsDB member countries (ISO 3166-1 alpha-3).
ISDB_MEMBERS = [
    "AFG", "ALB", "ARE", "AZE", "BEN", "BFA", "BGD", "BHR", "BRN", "CIV", "CMR", "COM",
    "DJI", "DZA", "EGY", "GAB", "GIN", "GMB", "GNB", "GUY", "IDN", "IRN", "IRQ", "JOR",
    "KAZ", "KGZ", "KWT", "LBN", "LBY", "MAR", "MDV", "MLI", "MOZ", "MRT", "MYS", "NER",
    "NGA", "OMN", "PAK", "PSE", "QAT", "SAU", "SDN", "SEN", "SLE", "SOM", "SUR", "SYR",
    "TCD", "TGO", "TJK", "TKM", "TUN", "TUR", "UGA", "UZB", "YEM",
]
# GADM keeps disputed areas as separate pseudo-countries. They keep their own
# GADM ids, are flagged disputed=1, and the Z0x areas get the ISO3 of the
# administering country (GADM's COUNTRY field) so country filters include them.
DISPUTED = {
    "Z01": "IND", "Z02": "CHN", "Z03": "CHN", "Z04": "IND", "Z05": "IND",
    "Z06": "PAK", "Z07": "IND", "Z08": "CHN", "Z09": "IND",
    "XKO": "XKO", "ZNC": "ZNC", "XPI": "XPI", "XSP": "XSP",
}

LEVELS = [0, 1, 2, 3]
# Simplification tolerance in degrees per level (~1 km, 500 m, 200 m, 100 m).
TOLERANCE = {0: 0.01, 1: 0.005, 2: 0.002, 3: 0.001}
COLUMNS = ["gid", "level", "iso3", "country", "name", "name_local", "type", "parent_gid",
           "name_1", "name_2", "name_3", "hasc", "disputed", "area_km2", "geometry"]
GEOD = Geod(ellps="WGS84")


def col(df: pd.DataFrame, name: str):
    return df[name] if name in df.columns else pd.Series([None] * len(df), index=df.index)


def clean(df: gpd.GeoDataFrame, level: int, gid0: str) -> gpd.GeoDataFrame:
    out = pd.DataFrame(index=df.index)
    out["gid"] = df[f"GID_{level}"]
    out["level"] = level
    out["iso3"] = DISPUTED.get(gid0, gid0)
    out["country"] = df["COUNTRY"]
    out["name"] = df["COUNTRY"] if level == 0 else df[f"NAME_{level}"]
    out["name_local"] = None if level == 0 else col(df, f"NL_NAME_{level}")
    out["type"] = "Country" if level == 0 else col(df, f"ENGTYPE_{level}")
    out["parent_gid"] = None if level == 0 else df[f"GID_{level - 1}"]
    for n in (1, 2, 3):
        out[f"name_{n}"] = col(df, f"NAME_{n}") if n <= level else None
    out["hasc"] = None if level == 0 else col(df, f"HASC_{level}")
    out["disputed"] = 1 if gid0 in DISPUTED else 0
    # Disputed areas keep their own GADM ids; level 0 gets a readable id.
    if level == 0 and gid0 in DISPUTED:
        out["gid"] = gid0
    geom = shapely.make_valid(df.geometry.values)
    # make_valid can return collections; keep the polygon parts as MultiPolygon.
    geom = [_as_multipolygon(g) for g in geom]
    # GADM 4.1 drops the dot after the country code in some ids (e.g. Ghana
    # "GHA1_2" instead of "GHA.1_2"); put it back so ids nest consistently.
    for c in ("gid", "parent_gid"):
        out[c] = out[c].map(_fix_gid)
    gdf = gpd.GeoDataFrame(out, geometry=geom, crs="EPSG:4326")
    gdf["area_km2"] = [round(abs(GEOD.geometry_area_perimeter(g)[0]) / 1e6, 3) if g else None
                       for g in gdf.geometry]
    gdf = gdf[~gdf.geometry.is_empty & gdf.geometry.notna()]
    # Drop GADM placeholders without a proper id (e.g. Ukraine's "?" unit).
    gdf = gdf[gdf["gid"].astype(str).str.match(r"^[A-Z0-9]{3}(\.[0-9.]+_\d+)?$")]
    for c in ("name", "name_local", "type", "name_1", "name_2", "name_3", "hasc"):
        gdf[c] = gdf[c].replace({"NA": None, "": None})
    return gdf[COLUMNS]


def _fix_gid(gid):
    if not isinstance(gid, str) or len(gid) <= 3 or gid[3] == ".":
        return gid
    return f"{gid[:3]}.{gid[3:]}"


def _as_multipolygon(g):
    if g is None or g.is_empty:
        return None
    if g.geom_type == "MultiPolygon":
        return g
    if g.geom_type == "Polygon":
        return shapely.MultiPolygon([g])
    polys = [p for p in shapely.get_parts(g) if p.geom_type in ("Polygon", "MultiPolygon")]
    parts = []
    for p in polys:
        parts.extend(shapely.get_parts(p))
    return shapely.MultiPolygon(parts) if parts else None


def simplify(gdf: gpd.GeoDataFrame, level: int) -> gpd.GeoDataFrame:
    tol = TOLERANCE[level]
    out = gdf.copy()
    try:
        # Simplifies the units as one coverage, so neighbours keep shared edges.
        out["geometry"] = shapely.coverage_simplify(gdf.geometry.values, tol)
    except Exception:
        out["geometry"] = shapely.simplify(gdf.geometry.values, tol, preserve_topology=True)
    out["geometry"] = [_as_multipolygon(shapely.make_valid(g)) for g in out.geometry]
    return out[out.geometry.notna()]


def _written(path: Path, layer: str) -> set[str]:
    """GADM country codes already in an output layer (for --resume)."""
    if not path.exists() or layer not in [n for n, _ in pyogrio.list_layers(path)]:
        return set()
    gids = pyogrio.read_dataframe(path, layer=layer, read_geometry=False, columns=["gid"])["gid"]
    return set(gids.str[:3])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("outdir")
    ap.add_argument("--countries", help="Comma-separated ISO3 list (default: IsDB members)")
    ap.add_argument("--isdb", action="store_true", help="Only the IsDB member countries")
    ap.add_argument("--resume", action="store_true",
                    help="Keep existing output and skip countries already written")
    ap.add_argument("--max-seconds", type=float, default=0,
                    help="Stop cleanly after this long (rerun with --resume to continue)")
    args = ap.parse_args()

    src = Path(args.source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    prefix = "gadm41_isdb_adm0-3" if args.isdb else "gadm41_adm0-3"
    full = outdir / f"{prefix}.gpkg"
    simp = outdir / f"{prefix}_simplified.gpkg"

    if args.countries:
        codes = [c.strip().upper() for c in args.countries.split(",")]
    elif args.isdb:
        codes = ISDB_MEMBERS + ["Z06"]
    else:
        codes = sorted(pyogrio.read_dataframe(src, layer="ADM_0", read_geometry=False)["GID_0"])

    started = time.time()
    summary = []
    for level in LEVELS:
        layer = f"adm{level}"
        done = _written(full, layer) if args.resume else set()
        first = not done
        # Row ids per country, read once without geometry: fetching rows by id
        # uses the primary key, unlike a WHERE on the unindexed GID_0 column.
        index = pyogrio.read_dataframe(src, layer=f"ADM_{level}", read_geometry=False,
                                       columns=["GID_0"], fid_as_index=True)
        fids_by_code = {c: list(g.index) for c, g in index.groupby("GID_0")}
        for code in codes:
            if code in done:
                continue
            if args.max_seconds and time.time() - started > args.max_seconds:
                print("paused: rerun with --resume", flush=True)
                return 2
            t = time.time()
            fids = fids_by_code.get(code)
            if not fids:
                summary.append((code, level, 0))
                continue
            df = pyogrio.read_dataframe(src, layer=f"ADM_{level}", fids=fids)
            if df.empty:
                summary.append((code, level, 0))
                continue
            gdf = clean(df, level, code)
            mode = "w" if first else "a"
            pyogrio.write_dataframe(gdf, full, layer=layer, driver="GPKG", append=not first,
                                    promote_to_multi=True)
            pyogrio.write_dataframe(simplify(gdf, level), simp, layer=layer, driver="GPKG",
                                    append=not first, promote_to_multi=True)
            first = False
            summary.append((code, level, len(gdf)))
            print(f"{layer} {code}: {len(gdf)} units ({time.time() - t:.1f}s)", flush=True)

    summary = []
    for level in LEVELS:
        try:
            gids = pyogrio.read_dataframe(full, layer=f"adm{level}", read_geometry=False,
                                          columns=["gid"])["gid"]
        except Exception:
            continue
        for code, n in gids.str[:3].value_counts().items():
            summary.append((code, level, int(n)))
    s = pd.DataFrame(summary, columns=["iso3", "level", "units"]).pivot_table(
        index="iso3", columns="level", values="units", fill_value=0)
    s = s.astype(int)
    s.columns = [f"adm{c}" for c in s.columns]
    s.to_csv(outdir / f"{prefix}_summary.csv")
    print(s.sum().to_string())
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
