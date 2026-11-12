"""OSM data layer: taxonomy, PBF header, Geofabrik region choice, GDAL extraction, Overpass fallback.

Offline: the "extract" is a small OSM XML file (GDAL's OSM driver reads XML and PBF
through the same code), and network calls are patched.
"""
import json
import struct
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, override_settings

from apps.analysis.data import osm
from apps.analysis.data import get_dataset
from apps.analysis.data.osm import extract, geofabrik, overpass, taxonomy
from apps.analysis.data.osm.pbf_header import snapshot_time

TMP = Path(tempfile.mkdtemp(prefix="geida-osm-test-"))
BBOX = (32.0, 1.0, 32.01, 1.01)

# Two schools (a node and a closed way), two buildings and one building=no, a road,
# and a clinic outside the box.
OSM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="geida-test">
  <node id="1" lat="1.005" lon="32.005" version="1"><tag k="amenity" v="school"/><tag k="name" v="Alpha Primary"/><tag k="isced:level" v="1"/></node>
  <node id="2" lat="1.0060" lon="32.0060" version="1"/>
  <node id="3" lat="1.0060" lon="32.0070" version="1"/>
  <node id="4" lat="1.0070" lon="32.0070" version="1"/>
  <node id="5" lat="1.0070" lon="32.0060" version="1"/>
  <node id="6" lat="1.0020" lon="32.0020" version="1"/>
  <node id="7" lat="1.0020" lon="32.0025" version="1"/>
  <node id="8" lat="1.0025" lon="32.0025" version="1"/>
  <node id="9" lat="1.0025" lon="32.0020" version="1"/>
  <node id="10" lat="1.0030" lon="32.0030" version="1"/>
  <node id="11" lat="1.0030" lon="32.0032" version="1"/>
  <node id="12" lat="1.0032" lon="32.0032" version="1"/>
  <node id="13" lat="1.0001" lon="32.0001" version="1"/>
  <node id="14" lat="1.0099" lon="32.0099" version="1"/>
  <node id="15" lat="1.5" lon="32.5" version="1"><tag k="amenity" v="clinic"/></node>
  <way id="100" version="1"><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="5"/><nd ref="2"/>
    <tag k="amenity" v="school"/><tag k="building" v="school"/><tag k="name" v="Beta Secondary"/></way>
  <way id="101" version="1"><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="9"/><nd ref="6"/><tag k="building" v="house"/></way>
  <way id="102" version="1"><nd ref="10"/><nd ref="11"/><nd ref="12"/><nd ref="10"/><tag k="building" v="no"/></way>
  <way id="103" version="1"><nd ref="13"/><nd ref="14"/><tag k="highway" v="primary"/><tag k="surface" v="asphalt"/></way>
</osm>
"""


def _varint(v):
    out = b""
    while True:
        b, v = v & 127, v >> 7
        out += bytes([b | (128 if v else 0)])
        if not v:
            return out


def _field(number, value):
    if isinstance(value, int):
        return _varint(number << 3) + _varint(value)
    return _varint(number << 3 | 2) + _varint(len(value)) + value


def _pbf_header(ts):
    header_block = _field(4, b"OsmSchema-V0.6") + _field(32, ts)
    blob = _field(1, header_block)
    blob_header = _field(1, b"OSMHeader") + _field(3, len(blob))
    return struct.pack(">I", len(blob_header)) + blob_header + blob


def _square(w, s, e, n):
    return {"type": "Polygon", "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]]}


@override_settings(DATA_DIR=TMP)
class TaxonomyTests(SimpleTestCase):
    def test_seed_file_parses(self):
        layers = taxonomy.layers()
        for lid in ("schools", "health", "buildings", "roads", "water_points", "power_lines"):
            self.assertIn(lid, layers)
        self.assertIn("amenity", taxonomy.all_keys())

    def test_match_and_exclude(self):
        b = taxonomy.get_layer("buildings")
        self.assertTrue(b.matches({"building": "yes"}))
        self.assertFalse(b.matches({"building": "no"}))
        self.assertFalse(b.matches({"amenity": "school"}))
        h = taxonomy.get_layer("health")
        self.assertTrue(h.matches({"healthcare": "clinic"}))
        self.assertFalse(h.matches({"amenity": "pharmacy"}))

    def test_bad_layer_is_rejected(self):
        with self.assertRaises(ValueError):
            taxonomy.parse({"layers": {"x": {"geometry": "blob", "match": [{"a": ["b"]}]}}})
        with self.assertRaises(ValueError):
            taxonomy.parse({"layers": {"x": {"geometry": "point", "match": []}}})


class PbfHeaderTests(SimpleTestCase):
    def test_snapshot_time_from_header(self):
        p = TMP / "h.osm.pbf"
        p.write_bytes(_pbf_header(1793567296))
        self.assertEqual(snapshot_time(p), datetime.fromtimestamp(1793567296, timezone.utc))
        self.assertEqual(geofabrik.snapshot(p), datetime.fromtimestamp(1793567296, timezone.utc).strftime("%Y-%m-%d"))

    def test_not_a_pbf(self):
        p = TMP / "x.osm"
        p.write_text("<osm/>")
        with self.assertRaises(ValueError):
            snapshot_time(p)


@override_settings(DATA_DIR=TMP)
class RegionTests(SimpleTestCase):
    INDEX = {"features": [
        {"properties": {"id": "africa", "name": "Africa", "urls": {"pbf": "https://x/africa.pbf"}},
         "geometry": _square(-20, -35, 55, 38)},
        {"properties": {"id": "uganda", "parent": "africa", "name": "Uganda", "urls": {"pbf": "https://x/uganda.pbf"}},
         "geometry": _square(29.5, -1.5, 35.0, 4.3)},
        {"properties": {"id": "kampala", "parent": "uganda", "name": "Kampala", "urls": {"pbf": "https://x/kla.pbf"}},
         "geometry": _square(32.4, 0.2, 32.7, 0.5)},
        {"properties": {"id": "no-pbf", "parent": "africa", "name": "No PBF", "urls": {}}, "geometry": _square(31, 0, 33, 2)},
    ]}

    def test_smallest_covering_region(self):
        r = geofabrik.find_region(BBOX, self.INDEX)
        self.assertEqual((r["id"], r["partial"]), ("uganda", False))
        self.assertEqual(geofabrik.find_region((32.5, 0.3, 32.6, 0.4), self.INDEX)["id"], "kampala")

    def test_continents_are_never_used(self):
        with self.assertRaises(geofabrik.GeofabrikUnavailable):
            geofabrik.find_region((10, 10, 11, 11), self.INDEX)  # only Africa covers it

    def test_no_region(self):
        with self.assertRaises(geofabrik.GeofabrikUnavailable):
            geofabrik.find_region((100, 10, 101, 11), self.INDEX)

    def test_box_across_border_uses_centre_country_partial(self):
        # A district on the Uganda-Kenya border plus a buffer: Uganda, flagged partial (not Africa).
        r = geofabrik.find_region((34.5, 1, 35.1, 1.1), self.INDEX)
        self.assertEqual((r["id"], r["partial"]), ("uganda", True))


@override_settings(DATA_DIR=TMP)
class ExtractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.src = TMP / "test.osm"
        cls.src.write_text(OSM_XML)
        cls.gpkg, cls.box = extract.area_gpkg(cls.src, "test", "2026-11-01", BBOX, log=lambda m: None)

    def _layer(self, lid, **kw):
        p = extract.themed_layer(self.gpkg, self.box, taxonomy.get_layer(lid), log=lambda m: None, **kw)
        return json.loads(Path(p).read_text())["features"]

    def test_snap_bbox_outward(self):
        self.assertEqual(extract.snap_bbox((32.001, 1.001, 32.011, 1.009)), (32.0, 1.0, 32.02, 1.02))

    def test_schools_from_nodes_and_areas(self):
        feats = self._layer("schools")
        self.assertEqual({f["properties"]["name"] for f in feats}, {"Alpha Primary", "Beta Secondary"})
        self.assertTrue(all(f["geometry"]["type"] == "Point" for f in feats))
        ids = {f["properties"]["osm_id"] for f in feats}
        self.assertEqual(ids, {"node/1", "way/100"})
        alpha = next(f for f in feats if f["properties"]["osm_id"] == "node/1")
        self.assertEqual(alpha["properties"]["isced:level"], "1")

    def test_buildings_exclude_and_points(self):
        polys = self._layer("buildings")
        self.assertEqual({f["properties"]["osm_id"] for f in polys}, {"way/100", "way/101"})  # building=no left out
        self.assertTrue(all(f["geometry"]["type"] in ("Polygon", "MultiPolygon") for f in polys))
        pts = self._layer("buildings", as_points=True)
        self.assertEqual(len(pts), 2)
        self.assertTrue(all(f["geometry"]["type"] == "Point" for f in pts))

    def test_roads_are_lines(self):
        roads = self._layer("roads")
        self.assertEqual(len(roads), 1)
        self.assertEqual(roads[0]["geometry"]["type"], "LineString")
        self.assertEqual(roads[0]["properties"]["surface"], "asphalt")

    def test_outside_box_is_excluded(self):
        self.assertEqual(self._layer("health"), [])

    def test_area_cache_is_reused(self):
        again, _ = extract.area_gpkg(self.src, "test", "2026-11-01", BBOX, log=lambda m: self.fail(m))
        self.assertEqual(again, self.gpkg)


@override_settings(DATA_DIR=TMP, OSM_SOURCE="geofabrik")
class FetchLayerTests(SimpleTestCase):
    def test_extract_path_and_meta(self):
        src = TMP / "fetch.osm"
        src.write_text(OSM_XML)
        region = {"id": "testland", "name": "Testland", "url": "https://x/testland.pbf"}
        with mock.patch.object(geofabrik, "find_region", return_value=region), \
                mock.patch.object(geofabrik, "ensure_extract", return_value=src), \
                mock.patch.object(geofabrik, "snapshot", return_value="2026-11-01"):
            path, meta = osm.fetch_layer("schools", BBOX, log=lambda m: None)
        self.assertEqual(meta["source"], "geofabrik")
        self.assertEqual(meta["snapshot"], "2026-11-01")
        self.assertEqual(len(json.loads(Path(path).read_text())["features"]), 2)

    def test_falls_back_to_overpass(self):
        feats = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [32.005, 1.005]},
                  "properties": {"osm_id": "node/1", "name": "A"}}]
        logs = []
        with mock.patch.object(geofabrik, "find_region", side_effect=geofabrik.GeofabrikUnavailable("offline")), \
                mock.patch.object(overpass, "fetch", return_value=feats):
            path, meta = osm.fetch_layer("schools", (40.0, 1.0, 40.01, 1.01), log=logs.append)
        self.assertEqual(meta["source"], "overpass")
        self.assertTrue(any("Overpass" in m for m in logs))
        self.assertEqual(json.loads(Path(path).read_text())["features"], feats)

    def test_both_sources_down(self):
        with mock.patch.object(geofabrik, "find_region", side_effect=geofabrik.GeofabrikUnavailable("offline")), \
                mock.patch.object(overpass, "fetch", side_effect=overpass.OverpassUnavailable("timeout")):
            with self.assertRaises(osm.OSMUnavailable):
                osm.fetch_layer("schools", (41.0, 1.0, 41.01, 1.01), log=lambda m: None)

    def test_dataset_describe_names_the_snapshot(self):
        ds = get_dataset("osm_schools")
        with mock.patch.object(osm, "fetch_layer", return_value=(TMP / "x.geojson", {
                "source": "geofabrik", "region": "Uganda", "snapshot": "2026-11-01"})):
            ds.fetch(BBOX, "ZZZ", log=lambda m: None)
        d = ds.describe()
        self.assertEqual((d["reference_date"], d["osm_source"], d["osm_region"]), ("2026-11-01", "geofabrik", "Uganda"))


class OverpassQueryTests(SimpleTestCase):
    def test_query_from_rules(self):
        q = overpass.query(taxonomy.get_layer("health"), BBOX)
        self.assertIn('nwr["amenity"~"^(hospital|clinic|doctors)$"](1.0,32.0,1.01,32.01);', q)
        self.assertIn("out center tags;", q)
        self.assertIn('way["building"]', overpass.query(taxonomy.get_layer("buildings"), BBOX))
