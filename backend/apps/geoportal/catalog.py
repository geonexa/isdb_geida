"""
Data Catalog layer catalogue and basemaps.

kind:
  cog      - cloud-optimised GeoTIFF(s) read where they are hosted, drawn by TiTiler
             (apps/geoportal/raster.py): "cog" says where the files are, "render" how to draw them.
             "overview": a WMS that draws the layer below its minzoom (pictures only)
  tiles    - VIEW ONLY: pictures from an outside tile service (NASA GIBS, Terrascope, Esri
             Wayback). "url" is an XYZ template; {period} is the chosen year/month/date and
             {release} a Wayback release. "export" instead: an ArcGIS ImageServer drawn tile by
             tile with exportImage (the year is its time filter). No values: these can't be
             clipped or analysed.
  xyz      - tile URL template, read in place from a public service
  wms      - OGC WMS layer
  arcgis_image - ArcGIS ImageServer (exportImage)
  geojson  - vector file served by GEIDA
  pmtiles  - vector tiles in one PMTiles archive read in place over HTTP range requests (per
             year: "pmtiles.url" with {year}); "pmtiles.layers" names the source layers with
             their zoom range and colour: "ramp" (linear, by "property"; "hide_zero" leaves 0 clear),
             "steps" (classes by "property") or one "color"; "outline" adds a line colour and
             "threshold_property" lets users hide features below a minimum value. Drawn in the browser (Data Catalog and
             project map); not cut to a project area (the browser can't clip polygons)
  planned  - in the catalogue, waiting for processing into GEIDA's cloud storage

A layer with a "cog" entry can be clipped to an area (toolbox, a project's data layers).
projects_only: computed on the fly from many files (slope, hillshade), so only drawn for a
project's area (Analyses → Data layers), not on the global Data Catalog page.
minzoom: tiled datasets (DEM, WorldCover) are drawn from this zoom in, so one tile reads a few files.

Optional per layer: "phases", the project phases the layer is offered in, in a project's
Analyses tab (preparation, implementation, completion). Without it a layer is offered in
all three; the same layer may be listed in several phases.
"""

BASEMAPS = [
    {
        "id": "light",
        "name": "Light",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        "thumb": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/3/3/4",
        "attribution": "&copy; Esri, HERE, Garmin, OpenStreetMap contributors",
        "maxZoom": 16,
    },
    {
        "id": "streets",
        "name": "Streets",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        "thumb": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/3/3/4",
        "attribution": "Tiles &copy; Esri, TomTom, Garmin, FAO, NOAA, USGS",
    },
    {
        "id": "satellite",
        "name": "Satellite",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "thumb": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/3/3/4",
        "attribution": "Imagery &copy; Esri, Maxar, Earthstar Geographics",
    },
    {
        "id": "sentinel2",
        "name": "Sentinel-2",
        "url": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
        "thumb": "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/3/3/4.jpg",
        "attribution": "Sentinel-2 cloudless 2020 by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2020)",
        "maxZoom": 15,
    },
    {
        "id": "terrain",
        "name": "Terrain",
        "url": "https://{a-c}.tile.opentopomap.org/{z}/{x}/{y}.png",
        "thumb": "https://a.tile.opentopomap.org/3/4/3.png",
        "attribution": "&copy; OpenStreetMap contributors, SRTM | &copy; OpenTopoMap (CC-BY-SA)",
        "maxZoom": 17,
    },
    {
        "id": "dark",
        "name": "Dark",
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}",
        "thumb": "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/3/3/4",
        "attribution": "&copy; Esri, HERE, Garmin, OpenStreetMap contributors",
        "maxZoom": 16,
    },
]

def _hex(colors):
    return ["#" + c for c in colors]


# Legend colours sampled from TiTiler's colour maps (same names as "colormap_name").
YLGNBU = ["FFFFD9", "E0F3B1", "97D6B8", "41B6C3", "1E80B8", "23429A", "081D58"]
GNBU = ["F7FCF0", "D9F0D4", "B4E1BA", "7BCCC3", "42A6CB", "1474B2", "084081"]
ORRD = ["FFF7EC", "FDE1BA", "FDC38C", "FC8D59", "E7533A", "BF100A", "7F0000"]
YLGN = ["FFFFE5", "EDF8B2", "BBE395", "78C679", "379E54", "0C713B", "004529"]
YLORRD = ["FFFFCC", "FEE692", "FEBF5A", "FD8D3C", "F33C25", "CA0922", "800026"]
TERRAIN = ["00C47C", "75E37D", "F5FD97", "C2B078", "825F55", "BFADA9", "FFFFFF"]  # terrain, rescaled -1300..4200 m
WORLDCOVER = [
    (10, "006400", "Tree cover"), (20, "FFBB22", "Shrubland"), (30, "FFFF4C", "Grassland"), (40, "F096FF", "Cropland"),
    (50, "FA0000", "Built-up"), (60, "B4B4B4", "Bare / sparse vegetation"), (70, "F0F0F0", "Snow and ice"),
    (80, "0064C8", "Permanent water"), (90, "0096A0", "Herbaceous wetland"), (95, "00CF75", "Mangroves"),
    (100, "FAE6A0", "Moss and lichen"),
]


def _rgba(hex_color):
    return [int(hex_color[i:i + 2], 16) for i in (0, 2, 4)] + [255]


GREENS = ["F7FCF5", "DBF1D5", "ADDEA7", "74C476", "37A055", "0C7734", "00441B"]
RDYLGN = ["A50026", "E95739", "FDBE6E", "FEFEBD", "B7E075", "4EB15D", "006837"]
BUGN = ["F7FCFD", "DDF2F2", "AADED2", "66C2A4", "37A265", "0C7734", "00441B"]
YLORBR = ["FFFFE5", "FEF0AE", "FECE65", "FE9929", "E1640E", "AA3C03", "662505"]
PUBU = ["FFF7FB", "E3E0EE", "B4C3DE", "74A9CF", "2585BA", "046199", "023858"]

WAPOR = "https://storage.googleapis.com/fao-gismgr-wapor-3-data/DATA/WAPOR-3/MAPSET/"
WAPOR_YEARS = list(range(2018, 2026))


def _wapor(id, mapset, name, res, period, colormap, rescale, palette, vmin, vmax, unit, desc, scale, **extra):
    """A WaPOR v3 layer read from FAO's COGs. Annual mapsets list their years; monthly (-M) and
    dekadal (-D) ones take their periods from FAO's catalogue (periods_from)."""
    annual = mapset.endswith("-A")
    layer = {"id": id, "scale": scale, "name": name, "source": f"FAO WaPOR v3 ({mapset.split('-')[0]})", "res": res,
             "period": period, "kind": "cog",
             "cog": {"url": WAPOR + f"{mapset}/WAPOR-3.{mapset}.{{year}}.tif", "unscale": True},
             "render": {"rescale": rescale, "colormap_name": colormap},
             "legend": {"type": "ramp", "palette": _hex(palette), "min": vmin, "max": vmax, "unit": unit},
             "attribution": WAPOR_NOTE, "desc": desc}
    if annual:
        layer.update(years=WAPOR_YEARS, year=2024)
    else:
        layer.update(periods_from=f"wapor:{mapset}", period_label="Dekad" if mapset.endswith("-D") else "Month")
    layer.update(extra)
    return layer
DEM = {"stac": "cop-dem-glo-30", "dtype": "Float32"}
WAPOR_NOTE = "FAO WaPOR v3, read from FAO's public cloud bucket (cloud-optimised GeoTIFF)"
NEXT_STEP = "Next step: processed into GEIDA's cloud storage as yearly cloud-optimised GeoTIFFs."

# Outside services used for display (see docs/open-map-services.md). Pictures only.
TERRASCOPE_WMS = "https://mapproxy.terrascope.be/mapproxy/service"
TERRASCOPE_WMTS = ("https://wmts.terrascope.be/?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER={layer}&STYLE=default"
                   "&TILEMATRIXSET=EPSG:3857&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}&FORMAT=image/png&TIME={time}")
MUNDIALIS_WMS = "https://ows.mundialis.de/osm/service"
GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/"
VIEW_ONLY = "View only: a picture from {who}. It can't be clipped, downloaded or used in analyses."


def _months(first, gaps=()):
    """["2010-01", ..., last full month] for monthly GIBS layers."""
    import datetime

    today = datetime.date.today()
    y, m = first
    out = []
    while (y, m) < (today.year, today.month):
        if f"{y}-{m:02d}" not in gaps:
            out.append(f"{y}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _terrascope(layer, time="2021-01-01"):
    return TERRASCOPE_WMTS.replace("{layer}", layer).replace("{time}", time)


NDVI_GIBS = ["F1ECEC", "D7C4B4", "AC8D73", "96BA20", "4E9401", "0A6900", "001801"]
LST_GIBS = ["C900FF", "2100FF", "00B3FF", "66FF12", "FFFF00", "FF7F00", "FF0100"]
GPW_GIBS = ["FFF2D1", "FFE0B0", "FCC677", "FBA54A", "F97534", "E83220", "BD0026"]
NDVI_MONTHS = _months((2010, 1), gaps={"2025-04"})

CATALOG = [
    {
        "type": "raster",
        "group": "Climate and water",
        "layers": [
            {"id": "precipitation", "scale": 5566, "name": "Annual Precipitation", "source": "FAO WaPOR v3 (L1, CHIRPS)", "res": "5 km",
             "period": "Annual total, 2017 to 2025", "kind": "cog", "years": list(range(2017, 2026)), "year": 2024,
             "cog": {"url": WAPOR + "L1-PCP-A/WAPOR-3.L1-PCP-A.{year}.tif", "unscale": True},
             "render": {"rescale": "0,2000", "colormap_name": "ylgnbu"},
             "legend": {"type": "ramp", "palette": _hex(YLGNBU), "min": "0", "max": "2000+", "unit": "mm/year"},
             "attribution": "CHIRPS precipitation, Climate Hazards Center UCSB, via " + WAPOR_NOTE,
             "desc": "Total rainfall for the year from satellite and station data (CHIRPS), as published in FAO WaPOR. Used for drought and water-balance analysis."},
            {"id": "eta", "scale": 300, "name": "Annual Actual Evapotranspiration", "source": "FAO WaPOR v3 (L1)", "res": "300 m",
             "period": "Annual, 2018 to 2025", "kind": "cog", "years": list(range(2018, 2026)), "year": 2024,
             "cog": {"url": WAPOR + "L1-AETI-A/WAPOR-3.L1-AETI-A.{year}.tif", "unscale": True},
             "render": {"rescale": "0,1500", "colormap_name": "gnbu"},
             "legend": {"type": "ramp", "palette": _hex(GNBU), "min": "0", "max": "1500+", "unit": "mm/year"},
             "attribution": WAPOR_NOTE,
             "desc": "Water actually used by crops and vegetation over the year (evaporation, transpiration and interception)."},
            {"id": "ret", "scale": 27750, "name": "Annual Reference Evapotranspiration", "source": "FAO WaPOR v3 (L1)", "res": "25 km",
             "period": "Annual, 2018 to 2025", "kind": "cog", "years": list(range(2018, 2026)), "year": 2024,
             "cog": {"url": WAPOR + "L1-RET-A/WAPOR-3.L1-RET-A.{year}.tif", "unscale": True},
             "render": {"rescale": "500,2500", "colormap_name": "orrd", "resampling": "bilinear"},
             "legend": {"type": "ramp", "palette": _hex(ORRD), "min": "500", "max": "2500+", "unit": "mm/year"},
             "attribution": WAPOR_NOTE,
             "desc": "How much water the atmosphere demands over the year (FAO Penman-Monteith). Compare with actual evapotranspiration to see water stress."},
            _wapor("transpiration", "L1-T-A", "Annual Transpiration", "300 m", "Annual, 2018 to 2025", "bugn",
                   "0,1200", BUGN, "0", "1200+", "mm/year",
                   "Water passing through plants over the year: the 'productive' part of evapotranspiration, linked to crop growth.", 300),
            _wapor("evaporation", "L1-E-A", "Annual Evaporation", "300 m", "Annual, 2018 to 2025", "ylorbr",
                   "0,800", YLORBR, "0", "800+", "mm/year",
                   "Water evaporating from the soil surface over the year: the 'non-productive' part of evapotranspiration.", 300),
            _wapor("interception", "L1-I-A", "Annual Interception", "300 m", "Annual, 2018 to 2025", "pubu",
                   "0,200", PUBU, "0", "200+", "mm/year",
                   "Rain caught on leaves that evaporates before reaching the soil, over the year.", 300),
            {"id": "surface-water", "name": "Surface water occurrence", "source": "JRC Global Surface Water", "res": "30 m",
             "period": "1984 to 2021", "kind": "xyz",
             "url": "https://storage.googleapis.com/global-surface-water/tiles2021/occurrence/{z}/{x}/{y}.png", "maxZoom": 13, "scale": 30,
             "cog": {"grid": "jrc", "dtype": "Byte"},
             "attribution": "Source: EC JRC / Google",
             "legend": {"type": "ramp", "palette": ["#FFF0F0", "#3A3AFF"], "min": "0%", "max": "100%", "unit": "of the time"},
             "desc": "How often each pixel was covered by water across 37 years of Landsat imagery."},
            {"id": "temperature", "name": "Air temperature", "source": "ERA5-Land", "res": "9 km", "period": "Annual mean, 1950 to 2025",
             "kind": "planned", "desc": "Mean near-surface air temperature for the year from climate reanalysis. " + NEXT_STEP},
        ],
    },
    {
        "type": "raster",
        "group": "Vegetation and land",
        "layers": [
            {"id": "landcover", "scale": 10, "name": "Land cover", "source": "ESA WorldCover", "res": "10 m", "period": "2020 and 2021",
             "kind": "cog", "years": [2020, 2021], "year": 2021, "minzoom": 7,
             "cog": {"grid": "worldcover", "dtype": "Byte", "nodata": 0},
             "overview": {"wms": TERRASCOPE_WMS, "layers": {"2020": "esa-worldcover-map-10m-2020-v1_map",
                                                             "2021": "esa-worldcover-map-10m-2021-v2_map"}},
             "render": {"colormap": {str(v): _rgba(c) for v, c, _ in WORLDCOVER}, "resampling": "nearest"},
             "legend": {"type": "classes", "items": [["#" + c, n] for _, c, n in WORLDCOVER]},
             "attribution": "ESA WorldCover 2020 and 2021 (CC BY 4.0), read from ESA's AWS bucket",
             "desc": "Global land-cover map with 11 classes at 10 m from Sentinel-1 and Sentinel-2. Below zoom 7 the map shows Terrascope's WorldCover WMS; from zoom 7 the 10 m files themselves."},
            {"id": "lulc-esri", "name": "Land use and land cover (yearly)", "source": "Esri / Impact Observatory", "res": "10 m",
             "period": "Yearly, 2017 to 2025", "kind": "tiles", "view_only": True, "years": list(range(2017, 2026)), "year": 2025,
             "export": {"url": "https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer",
                        "rendering_rule": "Cartographic Renderer for Visualization and Analysis"},
             "maxzoom": 18,
             "legend": {"type": "classes", "items": [["#419BDF", "Water"], ["#397D49", "Trees"], ["#7A87C6", "Flooded vegetation"],
                                                     ["#E49635", "Crops"], ["#C4281B", "Built area"], ["#A59B8F", "Bare ground"],
                                                     ["#A8EBFF", "Snow and ice"], ["#616161", "Clouds"], ["#E3E2C3", "Rangeland"]]},
             "attribution": "Esri, Impact Observatory, Microsoft (CC BY 4.0)",
             "desc": "A 10 m land use and land cover map for every year since 2017 from Sentinel-2 (9 classes). " + VIEW_ONLY.format(who="Esri's image service")},
            {"id": "cropland", "name": "Temporary crops", "source": "ESA WorldCereal", "res": "10 m", "period": "2021",
             "kind": "tiles", "view_only": True, "maxzoom": 18,
             "url": _terrascope("esa-worldcereal-temporarycrops-10m-2021-v1_classification"),
             "legend": {"type": "classes", "items": [["#E47C05", "Temporary crops"]]},
             "attribution": "ESA WorldCereal 2021 (CC BY 4.0), via Terrascope (VITO)",
             "desc": "Where annual crops were grown in 2021, mapped at 10 m. " + VIEW_ONLY.format(who="Terrascope's WMTS")},
            {"id": "irrigation", "name": "Irrigated cropland", "source": "ESA WorldCereal", "res": "10 m", "period": "2021",
             "kind": "tiles", "view_only": True, "maxzoom": 18,
             "url": _terrascope("esa-worldcereal-irrigation-10m-2021-v1_classification"),
             "legend": {"type": "classes", "items": [["#2D7FB8", "Irrigated (active)"]]},
             "attribution": "ESA WorldCereal 2021 (CC BY 4.0), via Terrascope (VITO)",
             "desc": "Actively irrigated cropland in 2021 at 10 m. " + VIEW_ONLY.format(who="Terrascope's WMTS")},
            {"id": "ndvi", "name": "Vegetation index (NDVI)", "source": "MODIS (NASA GIBS)", "res": "1 km", "period": "Monthly, 2010 to last month",
             "kind": "tiles", "view_only": True, "years": NDVI_MONTHS, "year": NDVI_MONTHS[-1], "period_label": "Month", "maxzoom": 7,
             "url": GIBS + "MODIS_Terra_L3_NDVI_Monthly/default/{period}-01/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png",
             "legend": {"type": "ramp", "palette": _hex(NDVI_GIBS), "min": "0", "max": "1", "unit": "NDVI"},
             "attribution": "MODIS Terra NDVI, NASA GIBS",
             "desc": "Monthly vegetation greenness. " + VIEW_ONLY.format(who="NASA GIBS") + " Values come later from processed files."},
            {"id": "lst", "name": "Land surface temperature (day)", "source": "MODIS (NASA GIBS)", "res": "5 km", "period": "Monthly, 2010 to last month",
             "kind": "tiles", "view_only": True, "years": _months((2010, 1)), "year": _months((2010, 1))[-1], "period_label": "Month", "maxzoom": 6,
             "url": GIBS + "MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day/default/{period}-01/GoogleMapsCompatible_Level6/{z}/{y}/{x}.png",
             "legend": {"type": "ramp", "palette": _hex(LST_GIBS), "min": "-73", "max": "77", "unit": "°C"},
             "attribution": "MODIS Terra land surface temperature, NASA GIBS",
             "desc": "Monthly mean daytime temperature of the land surface (not the air). " + VIEW_ONLY.format(who="NASA GIBS")},
        ],
    },
    {
        "type": "raster",
        "group": "Crop water productivity",
        "layers": [
            _wapor("biomass-global", "L1-TBP-A", "Annual Biomass Production", "300 m", "Annual, 2018 to 2025", "greens",
                   "0,21000", GREENS, "0", "21,000+", "kg/ha",
                   "Total biomass (dry matter) produced over the year, worldwide. A basis for yield estimates.", 300),
            {"id": "biomass", "scale": 100, "name": "Annual Biomass Production (100 m)", "source": "FAO WaPOR v3 (L2)", "res": "100 m",
             "period": "Annual, 2018 to 2025", "kind": "cog", "years": list(range(2018, 2026)), "year": 2024,
             "cog": {"url": WAPOR + "L2-TBP-A/WAPOR-3.L2-TBP-A.{year}.tif", "unscale": True},
             "render": {"rescale": "0,25000", "colormap_name": "ylgn"},
             "legend": {"type": "ramp", "palette": _hex(YLGN), "min": "0", "max": "25,000+", "unit": "kg/ha"},
             "attribution": WAPOR_NOTE,
             "desc": "Total biomass produced over the year, a basis for yield and water-productivity analysis. Covers Africa and the Near East."},
            _wapor("gbwp", "L1-GBWP-A", "Annual Gross Biomass Water Productivity", "300 m", "Annual, 2018 to 2025", "rdylgn",
                   "0,3", RDYLGN, "0", "3+", "kg/m³",
                   "Biomass produced per cubic metre of water evapotranspired (total water use). Supports CRI 3.4 (crop yield per unit of water).", 300),
            _wapor("nbwp", "L1-NBWP-A", "Annual Net Biomass Water Productivity", "300 m", "Annual, 2018 to 2025", "rdylgn",
                   "0,3", RDYLGN, "0", "3+", "kg/m³",
                   "Biomass produced per cubic metre of water transpired (productive water use only).", 300),
        ],
    },
    {
        "type": "raster",
        "group": "Terrain",
        "layers": [
            {"id": "elevation", "scale": 30, "name": "Elevation", "source": "Copernicus DEM GLO-30", "res": "30 m", "period": "Static",
             "kind": "cog", "minzoom": 8, "cog": DEM,
             "overview": {"wms": TERRASCOPE_WMS, "layers": "cop-dem-glo-90m-cog_dem"},
             "render": {"rescale": "-1300,4200", "colormap_name": "terrain"},
             "legend": {"type": "ramp", "palette": _hex(TERRAIN), "min": "0", "max": "4,200+", "unit": "m"},
             "attribution": "Copernicus DEM GLO-30 (ESA), found with Earth Search STAC and read from AWS Open Data",
             "desc": "Height above sea level at 30 m from zoom 8; below that, Terrascope's 90 m Copernicus DEM picture (its own colours)."},
            {"id": "slope", "scale": 30, "name": "Slope", "source": "Copernicus DEM GLO-30", "res": "30 m", "period": "Static",
             "kind": "cog", "minzoom": 8, "cog": DEM, "projects_only": True,
             "render": {"algorithm": "slope", "rescale": "0,30", "colormap_name": "ylorrd"},
             "legend": {"type": "ramp", "palette": _hex(YLORRD), "min": "0", "max": "30+", "unit": "degrees"},
             "attribution": "Derived from Copernicus DEM GLO-30 by TiTiler",
             "desc": "Steepness of the terrain, computed on the fly from the 30 m DEM. Useful for irrigation and site suitability. Zoom 8 and closer."},
            {"id": "hillshade", "scale": 30, "name": "Hillshade", "source": "Copernicus DEM GLO-30", "res": "30 m", "period": "Static",
             "kind": "cog", "minzoom": 8, "cog": DEM, "opacity": 0.6, "projects_only": True,
             "overview": {"wms": MUNDIALIS_WMS, "layers": "SRTM30-Hillshade"},
             "render": {"algorithm": "hillshade"},
             "attribution": "Derived from Copernicus DEM GLO-30 by TiTiler",
             "desc": "Shaded relief to read slopes and landforms under other layers. Below zoom 8: SRTM hillshade WMS by terrestris (© terrestris, SRTM)."},
        ],
    },
    {
        "type": "raster",
        "group": "Population and imagery",
        "layers": [
            {"id": "population", "name": "Population density", "source": "GPW v4 (NASA SEDAC, via GIBS)", "res": "1 km",
             "period": "2000 to 2020, every 5 years", "kind": "tiles", "view_only": True, "years": [2000, 2005, 2010, 2015, 2020],
             "year": 2020, "maxzoom": 7,
             "url": GIBS + "GPW_Population_Density_{period}/default/GoogleMapsCompatible_Level7/{z}/{y}/{x}.png",
             "legend": {"type": "ramp", "palette": _hex(GPW_GIBS), "min": "< 1", "max": "1000+", "unit": "people/km² (log scale)"},
             "attribution": "CIESIN Columbia University, GPW v4 (CC BY 4.0), NASA GIBS",
             "desc": "People per km² from national censuses. " + VIEW_ONLY.format(who="NASA GIBS") + " Counts for analyses come later from WorldPop/GHSL files."},
            {"id": "wayback", "name": "Satellite imagery by date", "source": "Esri World Imagery Wayback", "res": "0.3 to 1 m",
             "period": "Every release since 2014", "kind": "tiles", "view_only": True, "periods_from": "wayback",
             "period_label": "Date", "maxzoom": 19,
             "url": "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/{release}/{z}/{y}/{x}",
             "attribution": "Esri World Imagery Wayback (Maxar, Earthstar Geographics and others)",
             "desc": "Very high resolution imagery as published on each date: compare before and after project works. " + VIEW_ONLY.format(who="Esri Wayback")},
        ],
    },
    {
        "type": "vector",
        "group": "Boundaries",
        "layers": [
            {"id": "member-countries", "name": "IsDB member countries", "source": "GEIDA", "res": "Simplified", "period": "Current", "kind": "geojson",
             "url": "/data/isdb_member_countries.geojson", "default": True,
             "legend": {"type": "line", "color": "#0B3B47"},
             "desc": "Outlines of the 57 IsDB member countries. Click a country to see its name."},
            {"id": "admin", "name": "Admin boundaries (level 1 and 2)", "source": "geoBoundaries", "res": "Vector", "period": "Current", "kind": "planned",
             "desc": "Provinces and districts for zonal statistics and reporting."},
        ],
    },
    {
        "type": "vector",
        "group": "Infrastructure and services",
        "layers": [
            {"id": "roads", "name": "Roads", "source": "Overture Maps", "res": "Vector", "period": "Monthly", "kind": "planned",
             "desc": "Road network by class, for access and service-area analysis."},
            {"id": "health", "name": "Hospitals and health facilities", "source": "OpenStreetMap, healthsites.io", "res": "Points", "period": "Quarterly", "kind": "planned",
             "desc": "Health facilities for exposure and accessibility studies."},
            {"id": "buildings", "name": "Building footprints", "source": "Overture Maps", "res": "Vector", "period": "Monthly", "kind": "planned",
             "desc": "Building outlines for settlement and exposure mapping."},
        ],
    },
    {
        "type": "vector",
        "group": "Agriculture",
        "layers": [
            {"id": "ftw-fields", "name": "Field boundaries (Fields of The World)", "source": "Fields of The World, 2nd Edition",
             "res": "Field polygons (Sentinel-2, 10 m)", "period": "Yearly, 2017 to 2025", "kind": "pmtiles",
             "years": list(range(2017, 2026)), "year": 2025,
             "pmtiles": {
                 "url": "https://data.source.coop/ftw/global-data-2e/vector/{year}/fields-{year}.pmtiles",
                 "maxzoom": 13,
                 # Zoomed out: cells coloured by field density (% of land in fields), on the Fields of The World
                 # app's ramp; empty cells stay clear. From zoom 9: the fields, filterable by model score.
                 "layers": [
                     {"source_layer": "cells", "minzoom": 0, "maxzoom": 9, "property": "pct_covered",
                      "ramp": [[0, "#ff00ee"], [100, "#00ff00"]], "hide_zero": True},
                     {"source_layer": "fields", "minzoom": 9, "maxzoom": 24, "color": "#00ff00", "outline": "#007a00",
                      "threshold_property": "score"},
                 ],
             },
             "legend": {"type": "ramp", "palette": ["#ff00ee", "#00ff00"], "min": "0", "max": "100", "unit": "% of land in fields"},
             "attribution": "Fields of The World 2nd Edition (CC BY 4.0), via Source Cooperative",
             "desc": "Agricultural field boundaries predicted worldwide from Sentinel-2 quarterly mosaics by the Fields of The World model: "
                     "about 1.24 billion fields over nine years, each with a 0–100 confidence score. Zoomed out, the map shows field density "
                     "(the share of land in fields); from zoom 9 the field outlines appear. Model predictions, not surveyed or legal parcels."},
        ],
    },
]


# ---------------------------------------------------------------------------
# Toolbox: the curated GEIDA tool set (ids from the GeoLibre / Whitebox catalog).
# Any other tool is reachable with "Show all tools".
# ---------------------------------------------------------------------------
TOOLBOX = [
    {"group": "Terrain", "icon": "mountain", "tools": [
        {"id": "slope", "hint": "Steepness of the terrain. Use with an elevation layer.", "defaults": {"units": "degrees"}},
        {"id": "aspect", "hint": "Direction each slope faces (0 = north)."},
        {"id": "hillshade", "hint": "Shaded relief for reading landforms."},
        {"id": "contours_from_raster", "hint": "Contour lines from elevation.", "defaults": {"interval": 20}},
    ]},
    {"group": "Water and hydrology", "icon": "droplets", "tools": [
        {"id": "fill_depressions", "hint": "Fill sinks in a DEM before flow analysis."},
        {"id": "d8_pointer", "hint": "Flow direction for each cell."},
        {"id": "d8_flow_accum", "hint": "How many cells drain through each cell.", "defaults": {"out_type": "cells", "log_transform": True}},
        {"id": "extract_streams", "hint": "Stream network from flow accumulation.", "defaults": {"threshold": 1000}},
        {"id": "watershed", "hint": "Area draining to a point you place on the map."},
    ]},
    {"group": "Raster", "icon": "grid-3x3", "tools": [
        {"id": "reclass", "hint": "Group values into classes, e.g. slope bands."},
        {"id": "raster_to_vector_polygons", "hint": "Turn classes into polygons."},
    ]},
    {"group": "Vector", "icon": "spline", "tools": [
        {"id": "buffer_vector", "hint": "Zone around features. Distance in metres.", "defaults": {"distance": 1000}},
        {"id": "clip", "hint": "Keep the part of a layer inside another."},
        {"id": "intersect", "hint": "Overlap of two polygon layers."},
        {"id": "dissolve", "hint": "Merge polygons into one."},
        {"id": "centroid_vector", "hint": "Centre point of each feature."},
        {"id": "polygon_area", "hint": "Add an area field (square metres)."},
    ]},
]
