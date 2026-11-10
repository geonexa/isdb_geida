"""
Send geometries to SpatiaLite as WKB instead of WKT.

Django's SpatiaLite backend passes every geometry as text through
GeomFromText(). SpatiaLite's WKT parser has a fixed stack and gives up on large
boundaries ("Giving up.  Parser stack overflow"), so the insert gets NULL and
fails (e.g. GADM countries with thousands of islands). WKB is binary, has no
parser limit and is also faster. PostGIS is unaffected (it already uses EWKB).
"""
from django.contrib.gis.db.backends.base.adapter import WKTAdapter
from django.db.backends.sqlite3.base import Database


class SpatiaLiteWKBAdapter(WKTAdapter):
    def __init__(self, geom):  # noqa: D107 - keep WKTAdapter's interface
        self.wkb = bytes(geom.wkb)
        self.srid = geom.srid

    @property
    def wkt(self):  # used by __eq__/__hash__ and debugging only
        return self.wkb.hex()

    def __str__(self):
        return self.wkt

    def __conform__(self, protocol):
        if protocol is Database.PrepareProtocol:
            return self.wkb


def install():
    from django.contrib.gis.db.backends.spatialite.operations import SpatiaLiteOperations

    SpatiaLiteOperations.Adapter = SpatiaLiteWKBAdapter
    SpatiaLiteOperations.from_text = "GeomFromWKB"
