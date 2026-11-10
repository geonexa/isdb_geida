import math

from .. import osm
from .base import Dataset, DatasetUnavailable


class RasterTiles(Dataset):
    """A global raster published as tiled COGs; subclasses name the tiles for a bbox."""

    resampling = "average"  # rasterio Resampling name
    max_pixels = 25_000_000
    dtype = None

    def tile_urls(self, bbox):
        raise NotImplementedError

    def sources(self, bbox, iso3):
        local = self.local_files(iso3)
        if local:
            return [str(p) for p in local], "local"
        return [f"/vsicurl/{u}" for u in self.tile_urls(bbox)], "download"

    def fetch(self, bbox, iso3, log=print):
        out = self.cache_path(bbox, iso3, ".tif")
        if out.exists():
            return str(out)
        srcs, how = self.sources(bbox, iso3)
        from .. import raster  # rasterio is only needed when a run reads rasters
        log(f"{self.title}: reading {len(srcs)} {'local file' if how == 'local' else 'tile'}(s)")
        res = raster.read_bbox(srcs, bbox, max_pixels=self.max_pixels, resampling=self.resampling, dtype=self.dtype)
        if res is None:
            raise DatasetUnavailable(f"{self.title} has no data for this area.")
        arr, transform, nodata, factor = res
        if factor > 1:
            log(f"{self.title}: area is large, read at {factor:.1f}x coarser resolution")
        return raster.write_tif(out, arr, transform, nodata)


def _floor(v, step):
    return int(math.floor(v / step) * step)


class CopernicusDEM(RasterTiles):
    id = "copernicus_dem_30"
    title = "Copernicus DEM GLO-30"
    resolution = "30 m"
    version = "2021"
    reference_date = "2011-2015"
    citation = "Copernicus DEM GLO-30 © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, provided under COPERNICUS by the European Union and ESA"
    licence = "Copernicus DEM licence (free)"
    source = "https://copernicus-dem-30m.s3.amazonaws.com/"

    def tile_urls(self, bbox):
        w, s, e, n = bbox
        urls = []
        for lat in range(_floor(s, 1), _floor(n, 1) + 1):
            for lon in range(_floor(w, 1), _floor(e, 1) + 1):
                ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
                ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
                name = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
                urls.append(f"{self.source}{name}/{name}.tif")
        return urls


class WorldCover(RasterTiles):
    id = "esa_worldcover_2021"
    title = "ESA WorldCover 2021"
    resolution = "10 m"
    version = "v200"
    reference_date = "2021"
    citation = "ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (Zanaga et al. 2022)"
    licence = "CC BY 4.0"
    source = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
    resampling = "mode"
    CLASSES = {10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland", 50: "Built-up",
               60: "Bare / sparse vegetation", 70: "Snow and ice", 80: "Permanent water bodies",
               90: "Herbaceous wetland", 95: "Mangroves", 100: "Moss and lichen"}
    COLORS = {10: (0, 100, 0), 20: (255, 187, 34), 30: (255, 255, 76), 40: (240, 150, 255), 50: (250, 0, 0),
              60: (180, 180, 180), 70: (240, 240, 240), 80: (0, 100, 200), 90: (0, 150, 160),
              95: (0, 207, 117), 100: (250, 230, 160)}

    def tile_urls(self, bbox):
        w, s, e, n = bbox
        urls = []
        for lat in range(_floor(s, 3), _floor(n, 3) + 1, 3):
            for lon in range(_floor(w, 3), _floor(e, 3) + 1, 3):
                ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
                ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
                urls.append(f"{self.source}ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map.tif")
        return urls


class WorldPop(RasterTiles):
    id = "worldpop_2020"
    title = "WorldPop population 2020"
    resolution = "100 m"
    version = "Global_2000_2020 (unconstrained)"
    reference_date = "2020"
    citation = "WorldPop (www.worldpop.org). Global High Resolution Population Denominators Project, OPP1134076. doi:10.5258/SOTON/WP00671"
    licence = "CC BY 4.0"
    source = "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/"
    resampling = "sum"  # coarsening keeps the people count
    max_pixels = 40_000_000
    dtype = "float32"

    def sources(self, bbox, iso3):
        local = self.local_files(iso3)
        if local:
            return [str(p) for p in local], "local"
        return [f"/vsicurl/{self.source}{iso3.upper()}/{iso3.lower()}_ppp_2020.tif"], "download"


class OSMLayer(Dataset):
    """A layer of the OSM tag taxonomy (seeds/data/osm_taxonomy.yaml), from a Geofabrik extract or Overpass.

    Polygon layers are also offered as points (point on surface) under
    osm_<layer>_points, for modules that count or measure distances.
    """

    kind = "vector"
    citation = "© OpenStreetMap contributors (ODbL)"
    licence = "ODbL 1.0"
    source = "https://www.openstreetmap.org"
    reference_date = "snapshot"

    def __init__(self, layer, as_points=False):
        self.layer_id = layer.id
        self.as_points = as_points
        self.id = f"osm_{layer.id}" + ("_points" if as_points else "")
        self.title = f"{layer.label} (OpenStreetMap)" + (" as points" if as_points else "")
        self.resolution = "points" if as_points or layer.geometry == "point" else layer.geometry + "s"
        self._last = {}

    @property
    def version(self):
        return self._last.get("snapshot", "latest")

    def fetch(self, bbox, iso3, log=print):
        local = self.local_files(iso3)
        if local:
            log(f"{self.title}: using {local[0].name}")
            self._last = {"source": "local file", "snapshot": "local"}
            return str(local[0])
        try:
            path, meta = osm.fetch_layer(self.layer_id, bbox, as_points=self.as_points, log=log)
        except osm.OSMUnavailable as exc:
            raise DatasetUnavailable(f"OpenStreetMap data unavailable: {exc}") from exc
        self._last = meta
        return str(path)

    def describe(self):
        d = super().describe()
        if self._last:
            d.update({"reference_date": self._last.get("snapshot", ""), "osm_source": self._last.get("source", ""),
                      "osm_region": self._last.get("region", "")})
        return d


def _osm_datasets():
    out = []
    for layer in osm.layers().values():
        out.append(OSMLayer(layer))
        if layer.geometry == "polygon":
            out.append(OSMLayer(layer, as_points=True))
    return out


DATASETS = {d.id: d for d in (CopernicusDEM(), WorldCover(), WorldPop(), *_osm_datasets())}


def get_dataset(dataset_id):
    try:
        return DATASETS[dataset_id]
    except KeyError as exc:
        raise DatasetUnavailable(f"Unknown dataset '{dataset_id}'.") from exc
