"""
Place search for the map search button (GET /api/geoportal/search/?q=...&places=1).

Two sources, admin units first:
  - admin units (GADM, our own database): name matches, every request (search as you type);
  - places (towns, villages, features) from a Nominatim geocoder (settings.GEOCODER_URL, default
    OpenStreetMap's public instance), only with places=1, i.e. when the user presses Enter: the public
    instance's usage policy forbids search-as-you-type. Answers are cached for a day; the
    browser never calls the geocoder itself.
Each result: {name, detail, kind, source, bbox: [w, s, e, n], center: [lon, lat]}.
"""
import json
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.gis.db.models.functions import Envelope
from django.core.cache import cache
from django.db.models import Case, IntegerField, Value, When
from django.db.models.functions import Length
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.boundaries.models import AdminUnit

LEVELS = {0: "Country", 1: "Province / region", 2: "District", 3: "Sub-district"}
MAX_UNITS = 6
MAX_PLACES = 6
CACHE_S = 24 * 3600


def admin_units(q, limit=MAX_UNITS):
    qs = (AdminUnit.objects.filter(name__icontains=q)
          .annotate(box=Envelope("geom_display"), starts=Case(When(name__istartswith=q, then=Value(0)), default=Value(1),
                                                              output_field=IntegerField()), n=Length("name"))
          .order_by("starts", "level", "n", "name").only("gid", "name", "level", "country", "name_1", "name_2", "type"))
    out = []
    for u in qs[:limit]:
        if u.box is None:
            continue
        w, s, e, n = u.box.extent
        parents = [p for p in (u.name_2 if u.level > 2 else "", u.name_1 if u.level > 1 else "", u.country if u.level else "") if p]
        out.append({"name": u.name, "detail": ", ".join(parents), "kind": u.type or LEVELS.get(u.level, "Admin unit"),
                    "source": "admin", "bbox": [w, s, e, n], "center": [(w + e) / 2, (s + n) / 2]})
    return out


def places(q, limit=MAX_PLACES):
    key = f"geocode:{q.lower()}"
    hit = cache.get(key)
    if hit is not None:
        return hit
    url = f"{settings.GEOCODER_URL}?" + urllib.parse.urlencode({"q": q, "format": "jsonv2", "limit": limit})
    req = urllib.request.Request(url, headers={"User-Agent": settings.GEOCODER_USER_AGENT, "Accept-Language": "en"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310 (configured geocoder)
        found = json.load(resp)
    out, seen = [], set()
    for f in found:
        if (f.get("display_name"), f.get("type")) in seen:
            continue
        seen.add((f.get("display_name"), f.get("type")))
        s, n, w, e = (float(v) for v in f.get("boundingbox") or [f["lat"], f["lat"], f["lon"], f["lon"]])
        name, _, rest = (f.get("display_name") or "").partition(", ")
        out.append({"name": f.get("name") or name, "detail": rest, "kind": (f.get("type") or f.get("category") or "place").replace("_", " ").capitalize(),
                    "source": "osm", "bbox": [w, s, e, n], "center": [float(f["lon"]), float(f["lat"])]})
    cache.set(key, out, CACHE_S)
    return out


@require_GET
def place_search(request):
    q = " ".join((request.GET.get("q") or "").split())[:120]
    if len(q) < 2:
        return JsonResponse({"results": []})
    results = admin_units(q)
    note = ""
    if request.GET.get("places") == "1":
        try:
            results += places(q)
        except (OSError, ValueError) as exc:
            note = f"Place search is unavailable right now ({exc.__class__.__name__}); showing admin units only."
    return JsonResponse({"results": results, "note": note})
