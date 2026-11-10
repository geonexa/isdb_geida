from django.test import SimpleTestCase

from .catalog import BASEMAPS


class BasemapTests(SimpleTestCase):
    def test_basemaps_endpoint_matches_config(self):
        own = self.client.get("/api/geoportal/basemaps/").json()["basemaps"]
        self.assertEqual(own, BASEMAPS)
        self.assertEqual(own, self.client.get("/api/geoportal/config/").json()["basemaps"])

    def test_every_basemap_is_complete(self):
        ids = [b["id"] for b in BASEMAPS]
        self.assertEqual(len(ids), len(set(ids)))
        for b in BASEMAPS:
            for key in ("id", "name", "url", "thumb", "attribution"):
                self.assertTrue(b.get(key), f"{b.get('id')}: {key} missing")


import json  # noqa: E402
from unittest import mock  # noqa: E402
from urllib.parse import parse_qs, urlparse  # noqa: E402

import numpy as np  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon, Polygon  # noqa: E402
from django.test import TestCase  # noqa: E402

from apps.projects.models import Project, ProjectArea  # noqa: E402

from . import raster  # noqa: E402
from .catalog import CATALOG  # noqa: E402

LAYERS = {l["id"]: l for g in CATALOG for l in g["layers"]}
DEM_TILE = "https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/x.tif"


def dem_items(collection, bx, by):
    """Fake STAC block: 1° DEM tiles of 3600 px."""
    return [(DEM_TILE.format(lat=lat, lon=lon), (lon, lat, lon + 1, lat + 1), (3600, 3600))
            for lat in range(by, by + 5) for lon in range(bx, bx + 5)]


def tiff(width=4, height=3, bands=2, value=7.0, mask=255):
    from rasterio.io import MemoryFile
    from rasterio.transform import from_origin

    arr = np.full((bands, height, width), value, dtype="float32")
    if bands > 1:
        arr[-1] = mask
        arr[-1, 0, 0] = 0  # one invalid pixel
    with MemoryFile() as f:
        with f.open(driver="GTiff", width=width, height=height, count=bands, dtype="float32", crs="EPSG:32636",
                    transform=from_origin(560000, 260000, 30, 30)) as dst:
            dst.write(arr)
        return f.read()


class CatalogTests(TestCase):
    def test_no_earth_engine_left(self):
        kinds = {l["kind"] for l in LAYERS.values()}
        self.assertNotIn("gee", kinds)
        self.assertFalse(any("gee" in l or "aoi_gee" in l for l in LAYERS.values()))
        self.assertTrue(LAYERS["cropland"]["view_only"])  # WorldCereal: Terrascope pictures, not Earth Engine
        self.assertFalse(hasattr(settings, "EE_KEY"))

    def test_config_lists_clippable_layers(self):
        cfg = self.client.get("/api/geoportal/config/").json()
        ids = {c["id"] for c in cfg["clippable"]}
        self.assertTrue({"eta", "precipitation", "biomass", "landcover", "elevation", "surface-water"} <= ids)
        # Computed on the fly from many DEM tiles: project areas only, not the global page.
        portal = {l["id"] for g in cfg["catalog"] for l in g["layers"]}
        self.assertFalse({"slope", "hillshade"} & (portal | ids))
        self.assertNotIn("member-countries", ids)
        self.assertNotIn("ndvi", ids)  # planned until processed into GEIDA's storage

    def test_single_cog_tiles_go_straight_to_titiler(self):
        r = self.client.get("/api/geoportal/layers/eta/tiles/?year=2020").json()
        url = r["tiles"][0]
        self.assertTrue(url.startswith(settings.TITILER_URL + "/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png?"))
        q = parse_qs(urlparse(url).query)
        self.assertTrue(q["url"][0].endswith("L1-AETI-A/WAPOR-3.L1-AETI-A.2020.tif"))
        self.assertEqual(q["unscale"], ["true"])
        self.assertEqual(q["colormap_name"], ["gnbu"])
        self.assertEqual(r["year"], 2020)

    def test_bad_year_is_a_400(self):
        r = self.client.get("/api/geoportal/layers/eta/tiles/?year=1900")
        self.assertEqual(r.status_code, 400)
        self.assertIn("1900", r.json()["error"])

    def test_tiled_dataset_uses_geida_tile_route(self):
        r = self.client.get("/api/geoportal/layers/slope/tiles/").json()
        self.assertEqual(r["tiles"], ["/api/geoportal/layers/slope/xyz/{z}/{x}/{y}.png"])
        self.assertEqual(r["minzoom"], 8)  # no WMS overview for slope

    def test_tile_below_minzoom_is_empty(self):
        r = self.client.get("/api/geoportal/layers/slope/xyz/3/4/3.png")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, raster.empty_png())

    def test_tile_mosaics_stac_items_in_a_vrt(self):
        with mock.patch.object(raster, "_stac_block", side_effect=dem_items):
            # z9 tile around 34.4E 2.3N (covers parts of 1-4 DEM tiles)
            r = self.client.get("/api/geoportal/layers/slope/xyz/9/304/253.png")
        self.assertEqual(r.status_code, 302)
        q = parse_qs(urlparse(r["Location"]).query)
        self.assertTrue(q["url"][0].startswith("<VRTDataset"))
        self.assertIn("/vsicurl/https://copernicus-dem-30m", q["url"][0])
        self.assertEqual(q["algorithm"], ["slope"])


class RasterTests(TestCase):
    def test_vrt_places_tiles_side_by_side(self):
        found = [("a.tif", (34, 2, 35, 3), (3600, 3600)), ("b.tif", (35, 2, 36, 3), (3600, 3600)),
                 ("c.tif", (34, 1, 35, 2), (3600, 3600))]
        x = raster._vrt(found, "Float32", None)
        self.assertIn('rasterXSize="7200" rasterYSize="7200"', x)
        self.assertIn('/vsicurl/b.tif</SourceFilename><SourceBand>1</SourceBand>'
                      '<SrcRect xOff="0" yOff="0" xSize="3600" ySize="3600"/><DstRect xOff="3600" yOff="0"', x)
        self.assertIn('<DstRect xOff="0" yOff="3600"', x)

    def test_too_many_files_is_refused(self):
        with mock.patch.object(raster, "_stac_block", side_effect=dem_items):
            with self.assertRaisesMessage(raster.RasterError, "too large"):
                raster.dataset(LAYERS["elevation"], None, (30, 0, 40, 10))

    def test_worldcover_tiles_by_grid(self):
        with mock.patch.object(raster, "_worldcover_tiles", return_value=frozenset({"N00E033", "S03E033"})):
            hrefs = [h for h, *_ in raster.sources(LAYERS["landcover"], 2021, (33.5, -1, 34.5, 1))]
        self.assertEqual(len(hrefs), 2)
        self.assertTrue(hrefs[0].endswith("v200/2021/map/ESA_WorldCover_10m_2021_v200_S03E033_Map.tif"))

    def test_jrc_tile_names(self):
        hrefs = [h for h, *_ in raster.sources(LAYERS["surface-water"], None, (34.2, 2.1, 34.6, 2.5))]
        self.assertEqual(hrefs, [raster.JRC_URL.format(lon="30E", lat="10N")])

    def test_png_round_trip_and_mask(self):
        rgba = np.zeros((256, 256, 4), dtype=np.uint8)
        rgba[..., 0], rgba[..., 3] = 200, 255
        back = raster.decode_rgba(raster.png_rgba(rgba))
        self.assertTrue((back == rgba).all())
        _, merc = raster.tile_bounds(9, 304, 253)
        left_half = Polygon.from_bbox((merc[0], merc[1], (merc[0] + merc[2]) / 2, merc[3]))
        left_half.srid = 3857
        out = raster.decode_rgba(raster.masked_tile(raster.png_rgba(rgba), left_half, merc))
        self.assertEqual(out[128, 10, 3], 255)
        self.assertEqual(out[128, 250, 3], 0)

    def test_clip_writes_float_geotiff_with_nodata(self):
        from rasterio.io import MemoryFile

        geom = GEOSGeometry("POLYGON((34.3 2.3,34.31 2.3,34.31 2.31,34.3 2.31,34.3 2.3))", srid=4326)
        with mock.patch.object(raster, "fetch", return_value=tiff()) as fetch:
            data, info = raster.clip_geotiff(LAYERS["eta"], 2024, geom)
        url = fetch.call_args.args[0]
        self.assertIn("/cog/bbox/", url)
        self.assertIn("dst_crs=EPSG%3A32636", url)
        self.assertEqual(info["epsg"], 32636)
        with MemoryFile(data) as f, f.open() as src:
            self.assertEqual(src.count, 1)
            self.assertEqual(src.nodata, raster.NODATA)
            band = src.read(1)
        self.assertEqual(band[0, 0], raster.NODATA)
        self.assertEqual(band[1, 1], 7.0)


class ProjectSatelliteTests(TestCase):
    """Catalogue rasters cut to a project's area of influence (apps/geoportal/project_rs.py)."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("o", "o@example.org", "pw-123456!")
        cls.p = Project.objects.create(code="UGA1072", title="t", country_iso3="UGA", country_name="Uganda", owner=cls.owner)
        ProjectArea.objects.create(project=cls.p, method="draw", area_km2=100,
                                   geom=MultiPolygon(Polygon.from_bbox((32.5, 0.2, 32.7, 0.4)), srid=4326))
        cls.bare = Project.objects.create(code="UGA2000", title="t", country_iso3="UGA", country_name="Uganda", owner=cls.owner)

    def setUp(self):
        self.client.force_login(self.owner)

    def test_lists_cog_rasters_by_group(self):
        groups = self.client.get("/api/projects/UGA1072/satellite/").json()["groups"]
        ids = [l["id"] for g in groups for l in g["layers"]]
        self.assertIn("eta", ids)
        self.assertIn("surface-water", ids)
        self.assertIn("hillshade", ids)  # projects_only layers are offered here
        self.assertIn("slope", ids)
        self.assertNotIn("temperature", ids)  # planned
        self.assertNotIn("member-countries", ids)

    def test_needs_access_and_an_area(self):
        self.client.logout()
        self.assertEqual(self.client.get("/api/projects/UGA1072/satellite/").status_code, 404)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get("/api/projects/UGA2000/satellite/").status_code, 400)
        self.assertEqual(self.client.get("/api/projects/UGA1072/satellite/nope/tiles/").status_code, 404)

    def test_tiles_template_and_bad_year(self):
        r = self.client.get("/api/projects/UGA1072/satellite/eta/tiles/?year=2024").json()
        self.assertTrue(r["tiles"][0].startswith("/api/projects/UGA1072/satellite/eta/xyz/{z}/{x}/{y}.png?v="))
        self.assertTrue(r["tiles"][0].endswith("&year=2024"))
        self.assertEqual(self.client.get("/api/projects/UGA1072/satellite/eta/tiles/?year=1900").status_code, 400)

    def test_tiles_outside_inside_and_across_the_area(self):
        base = "/api/projects/UGA1072/satellite/eta/xyz/"
        # far away: empty
        self.assertEqual(self.client.get(base + "9/10/10.png?year=2024").content, raster.empty_png())
        # z14 tile at 32.6E 0.3N is inside the 0.2° square: redirect to TiTiler
        r = self.client.get(base + "14/9675/8178.png?year=2024")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith(settings.TITILER_URL))
        # z8 tile contains the whole square: fetched and masked here
        solid = np.full((256, 256, 4), 255, dtype=np.uint8)
        with mock.patch.object(raster, "fetch", return_value=raster.png_rgba(solid)):
            r = self.client.get(base + "8/151/127.png?year=2024")
        self.assertEqual(r.status_code, 200)
        alpha = raster.decode_rgba(r.content)[..., 3]
        self.assertTrue(0 < (alpha > 0).sum() < alpha.size)

    def test_continuous_layers_offer_palette_and_range(self):
        layers = {l["id"]: l for g in self.client.get("/api/projects/UGA1072/satellite/").json()["groups"] for l in g["layers"]}
        self.assertEqual(layers["eta"]["style"]["cmap"], "gnbu")
        self.assertEqual(layers["eta"]["style"]["range"], [0, 1500])
        self.assertNotIn("style", layers["landcover"])  # classes keep their own colours

    def test_palette_and_range_reach_the_tile_server(self):
        r = self.client.get("/api/projects/UGA1072/satellite/eta/tiles/?year=2024&cmap=viridis_r&range=0,900").json()
        self.assertIn("cmap=viridis_r", r["tiles"][0])
        self.assertIn("range=0%2C900", r["tiles"][0])
        r = self.client.get("/api/projects/UGA1072/satellite/eta/xyz/14/9675/8178.png?year=2024&cmap=viridis_r&range=0,900")
        self.assertEqual(r.status_code, 302)
        self.assertIn("colormap_name=viridis_r", r["Location"])
        self.assertIn("rescale=0%2C900", r["Location"])

    def test_field_boundaries_are_vector_tiles(self):
        layers = {l["id"]: l for g in self.client.get("/api/projects/UGA1072/satellite/").json()["groups"] for l in g["layers"]}
        ftw = layers["ftw-fields"]
        self.assertEqual(ftw["kind"], "pmtiles")
        self.assertIn("{year}", ftw["pmtiles"]["url"])
        self.assertEqual([l["source_layer"] for l in ftw["pmtiles"]["layers"]], ["cells", "fields"])
        self.assertEqual(ftw["legend"]["type"], "ramp")  # field density, as in the FTW app
        # Read by the browser from the archive: no GEIDA tiles or GeoTIFF.
        self.assertEqual(self.client.get("/api/projects/UGA1072/satellite/ftw-fields/tiles/?year=2025").status_code, 400)
        self.assertEqual(self.client.get("/api/projects/UGA1072/satellite/ftw-fields/download/?year=2025").status_code, 400)

    def test_layers_carry_their_phases(self):
        from . import project_rs

        layers = {l["id"]: l for g in self.client.get("/api/projects/UGA1072/satellite/").json()["groups"] for l in g["layers"]}
        self.assertEqual(layers["eta"]["phases"], ["preparation", "implementation", "completion"])  # default: all
        self.assertEqual(project_rs._phases({"phases": ["completion", "nonsense"]}), ["completion"])

    def test_bad_palette_or_range_is_a_400(self):
        base = "/api/projects/UGA1072/satellite/eta/tiles/?year=2024"
        self.assertEqual(self.client.get(base + "&cmap=rainbow-unicorn").status_code, 400)
        self.assertEqual(self.client.get(base + "&range=900,0").status_code, 400)
        self.assertEqual(self.client.get(base + "&range=abc").status_code, 400)

    def test_download_is_masked_to_the_area(self):
        with mock.patch.object(raster, "fetch", return_value=tiff(width=20, height=20, value=5.0)):
            r = self.client.get("/api/projects/UGA1072/satellite/eta/download/?year=2024")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Disposition"], 'attachment; filename="UGA1072_eta_2024.tif"')


class ViewOnlyLayerTests(TestCase):
    """Pictures from outside services (NASA GIBS, Terrascope, Esri) and WMS overviews of COG layers."""

    def test_view_only_layers_are_not_clippable(self):
        cfg = self.client.get("/api/geoportal/config/").json()
        clip = {c["id"] for c in cfg["clippable"]}
        for lid in ("ndvi", "lst", "population", "wayback", "lulc-esri", "cropland", "irrigation"):
            self.assertEqual(LAYERS[lid]["kind"], "tiles")
            self.assertTrue(LAYERS[lid]["view_only"])
            self.assertNotIn(lid, clip)
        r = self.client.post("/api/geoportal/layers/ndvi/clip/", '{"geometry": {"type": "Point", "coordinates": [0, 0]}}',
                             content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_gibs_month_goes_into_the_template(self):
        month = LAYERS["ndvi"]["years"][-3]
        r = self.client.get(f"/api/geoportal/layers/ndvi/tiles/?year={month}").json()
        self.assertEqual(r["tiles"], [f"https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/MODIS_Terra_L3_NDVI_Monthly/default/"
                                      f"{month}-01/GoogleMapsCompatible_Level7/{{z}}/{{y}}/{{x}}.png"])
        self.assertEqual((r["maxzoom"], r["view_only"], r["year"]), (7, True, month))
        self.assertEqual(self.client.get("/api/geoportal/layers/ndvi/tiles/?year=1990-01").status_code, 400)

    def test_population_year_picks_the_gibs_layer(self):
        r = self.client.get("/api/geoportal/layers/population/tiles/?year=2010").json()
        self.assertIn("GPW_Population_Density_2010/default/", r["tiles"][0])

    def test_overview_wms_below_minzoom(self):
        r = self.client.get("/api/geoportal/layers/elevation/tiles/").json()
        self.assertEqual(r["minzoom"], 0)  # drawn at every zoom now
        r = self.client.get("/api/geoportal/layers/elevation/xyz/5/19/15.png")
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r["Location"].startswith("https://mapproxy.terrascope.be/mapproxy/service?"))
        self.assertIn("LAYERS=cop-dem-glo-90m-cog_dem", r["Location"])
        r = self.client.get("/api/geoportal/layers/landcover/xyz/5/19/15.png?year=2020")
        self.assertIn("esa-worldcover-map-10m-2020-v1_map", r["Location"])
        self.assertEqual(self.client.get("/api/geoportal/layers/slope/xyz/5/19/15.png").content, raster.empty_png())

    def test_esri_land_cover_tiles_use_export_image_with_the_year(self):
        r = self.client.get("/api/geoportal/layers/lulc-esri/tiles/?year=2019").json()
        self.assertEqual(r["tiles"], ["/api/geoportal/layers/lulc-esri/xyz/{z}/{x}/{y}.png?year=2019"])
        r = self.client.get("/api/geoportal/layers/lulc-esri/xyz/9/304/253.png?year=2019")
        q = parse_qs(urlparse(r["Location"]).query)
        self.assertTrue(r["Location"].startswith("https://ic.imagery1.arcgis.com/"))
        self.assertEqual(q["time"], ["1546300800000,1577836740000"])
        self.assertIn("Cartographic Renderer", q["renderingRule"][0])

    def test_wayback_dates_come_from_the_service(self):
        with mock.patch.object(raster, "wayback_releases", return_value={"2024-06-27": "111", "2025-01-30": "222"}):
            cfg = self.client.get("/api/geoportal/config/").json()
            wb = next(l for g in cfg["catalog"] for l in g["layers"] if l["id"] == "wayback")
            self.assertEqual((wb["years"], wb["year"]), (["2024-06-27", "2025-01-30"], "2025-01-30"))
            r = self.client.get("/api/geoportal/layers/wayback/tiles/?year=2024-06-27").json()
        self.assertTrue(r["tiles"][0].endswith("/MapServer/tile/111/{z}/{y}/{x}"))

    def test_wayback_unavailable_is_a_clear_error(self):
        with mock.patch.object(raster, "wayback_releases", return_value={}):
            r = self.client.get("/api/geoportal/layers/wayback/tiles/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("dates", r.json()["error"])


class ProjectViewOnlyTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_user("o", "o@example.org", "pw-123456!")
        cls.p = Project.objects.create(code="UGA1072", title="t", country_iso3="UGA", country_name="Uganda", owner=cls.owner)
        ProjectArea.objects.create(project=cls.p, method="draw", area_km2=100,
                                   geom=MultiPolygon(Polygon.from_bbox((32.5, 0.2, 32.7, 0.4)), srid=4326))

    def setUp(self):
        self.client.force_login(self.owner)

    def test_listed_with_view_only_flag_and_no_download(self):
        groups = self.client.get("/api/projects/UGA1072/satellite/").json()["groups"]
        layers = {l["id"]: l for g in groups for l in g["layers"]}
        self.assertTrue(layers["ndvi"]["view_only"])
        self.assertEqual(layers["ndvi"]["period_label"], "Month")
        self.assertNotIn("view_only", layers["eta"])
        r = self.client.get("/api/projects/UGA1072/satellite/ndvi/download/")
        self.assertEqual(r.status_code, 400)
        self.assertIn("view only", r.json()["error"])

    def test_tiles_inside_redirect_to_the_service(self):
        t = self.client.get("/api/projects/UGA1072/satellite/population/tiles/?year=2020").json()
        self.assertEqual(t["maxzoom"], 7)
        # z14 tile inside the area: GIBS URL (the map overzooms level 7, but the route still answers)
        r = self.client.get("/api/projects/UGA1072/satellite/population/xyz/7/139/63.png?year=2020")
        self.assertIn(r.status_code, (200, 302))


class WaporLayerTests(TestCase):
    """WaPOR v3 layers read from FAO's COGs; monthly and dekadal periods come from FAO's catalogue."""

    def test_annual_layers(self):
        for lid, mapset in [("transpiration", "L1-T-A"), ("evaporation", "L1-E-A"), ("interception", "L1-I-A"),
                            ("biomass-global", "L1-TBP-A"), ("gbwp", "L1-GBWP-A"), ("nbwp", "L1-NBWP-A")]:
            r = self.client.get(f"/api/geoportal/layers/{lid}/tiles/?year=2019").json()
            q = parse_qs(urlparse(r["tiles"][0]).query)
            self.assertTrue(q["url"][0].endswith(f"{mapset}/WAPOR-3.{mapset}.2019.tif"), lid)
            self.assertEqual(q["unscale"], ["true"])

    def test_only_annual_wapor_layers_named_annual(self):
        from .catalog import CATALOG

        wapor = [l for g in CATALOG for l in g["layers"] if "WAPOR-3" in str(l.get("cog", {}).get("url", ""))]
        self.assertEqual(len(wapor), 10)
        for l in wapor:
            self.assertIn("-A/", l["cog"]["url"], l["id"])  # annual mapsets only, for now
            self.assertTrue(l["name"].startswith("Annual "), l["name"])

    def test_fao_catalogue_paging(self):
        pages = [
            {"response": {"items": [{"code": "WAPOR-3.L1-PCP-M.2024-06"}],
                          "links": [{"rel": "next", "href": "https://next"}]}},
            {"response": {"items": [{"code": "WAPOR-3.L1-PCP-M.2024-05"}], "links": []}},
        ]

        class Resp:
            def __init__(self, body):
                self.body = json.dumps(body).encode()

            def read(self, *a):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        from django.core.cache import cache
        cache.delete("wapor:periods:L1-PCP-M")
        with mock.patch("urllib.request.urlopen", side_effect=[Resp(p) for p in pages]):
            self.assertEqual(raster.wapor_periods("L1-PCP-M"), ["2024-05", "2024-06"])
        cache.delete("wapor:periods:L1-PCP-M")
