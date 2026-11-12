"""Fixed lists used by project onboarding (shared by the API, the import and the UI)."""
import json
from functools import lru_cache

from django.conf import settings

SECTORS = [
    ("agriculture", "Agriculture"),
    ("water", "Water"),
    ("energy", "Energy"),
    ("transport", "Transport"),
    ("education", "Education"),
    ("health", "Health"),
    ("urban", "Urban development"),
    ("infrastructure", "Infrastructure"),
    ("finance", "Line of finance"),
    ("other", "Other"),
]

THEMES = [
    ("water", "Water"),
    ("agriculture", "Agriculture"),
    ("education", "Education"),
    ("health", "Health"),
    ("transport", "Transport"),
    ("energy", "Energy"),
    ("urban", "Urban"),
    ("infrastructure", "Infrastructure"),
]

# IsDB project-cycle instruments.
STAGES = [
    ("PCN", "PCN – Project Concept Note"),
    ("PPRR", "PPRR – Project Preparation"),
    ("PAD", "PAD – Appraisal"),
    ("PIASR", "PIASR – Implementation"),
    ("PCR", "PCR – Completion"),
    ("PPER", "PPER – Post-evaluation"),
]

HUBS = [
    ("HQ", "IsDB Headquarters, Jeddah"),
    ("Abuja", "Regional Hub – Abuja (Nigeria)"),
    ("Almaty", "Regional Hub – Almaty (Kazakhstan)"),
    ("Ankara", "Regional Hub – Ankara (Türkiye)"),
    ("Cairo", "Regional Hub – Cairo (Egypt)"),
    ("Dakar", "Regional Hub – Dakar (Senegal)"),
    ("Dhaka", "Regional Hub – Dhaka (Bangladesh)"),
    ("Jakarta", "Regional Hub – Jakarta (Indonesia)"),
    ("Kampala", "Regional Hub – Kampala (Uganda)"),
    ("Paramaribo", "Regional Hub – Paramaribo (Suriname)"),
    ("Rabat", "Regional Hub – Rabat (Morocco)"),
    ("KualaLumpur", "Centre of Excellence – Kuala Lumpur (Malaysia)"),
    ("Other", "Other"),
]

STATUSES = [("draft", "Draft"), ("review", "Under review"), ("published", "Published")]
SOURCES = [("manual", "Manual entry"), ("import", "Bulk import"), ("form", "Submission form")]
AREA_METHODS = [
    ("upload", "Uploaded file"),
    ("draw", "Drawn on the map"),
    ("admin", "Administrative units"),
    ("buffer", "Point with buffer"),
    ("country", "Whole country"),
]

LEVELS = [("impact", "Impact"), ("outcome", "Outcome"), ("output", "Output")]
TIERS = [
    ("project_cri", "Project CRI"),
    ("ta_cri", "TA CRI"),
    ("project_specific", "Project-specific"),
]
GEO_ROLES = [
    ("measure", "Measure"),
    ("estimate", "Estimate"),
    ("verify", "Verify"),
    ("context", "Context"),
    ("recorded", "Recorded"),
    ("none", "None"),
]
DOC_TYPES = [
    ("PCN", "PCN"),
    ("PAD", "PAD / appraisal"),
    ("PIASR", "PIASR"),
    ("PCR", "PCR"),
    ("map", "Map"),
    ("boundary", "Boundary file"),
    ("other", "Other"),
]
# TA CRIs (reported by a GEIDA TA component itself), per the development plan.
TA_CRI_CODES = {"17.1", "17.2", "17.4"}

ISO2_TO_ISO3 = {
    "AF": "AFG", "AL": "ALB", "DZ": "DZA", "AZ": "AZE", "BH": "BHR", "BD": "BGD", "BJ": "BEN",
    "BN": "BRN", "BF": "BFA", "CM": "CMR", "TD": "TCD", "KM": "COM", "CI": "CIV", "DJ": "DJI",
    "EG": "EGY", "GA": "GAB", "GM": "GMB", "GN": "GIN", "GW": "GNB", "GY": "GUY", "ID": "IDN",
    "IR": "IRN", "IQ": "IRQ", "JO": "JOR", "KZ": "KAZ", "KW": "KWT", "KG": "KGZ", "LB": "LBN",
    "LY": "LBY", "MY": "MYS", "MV": "MDV", "ML": "MLI", "MR": "MRT", "MA": "MAR", "MZ": "MOZ",
    "NE": "NER", "NG": "NGA", "OM": "OMN", "PK": "PAK", "PS": "PSE", "QA": "QAT", "SA": "SAU",
    "SN": "SEN", "SL": "SLE", "SO": "SOM", "SD": "SDN", "SR": "SUR", "SY": "SYR", "TJ": "TJK",
    "TG": "TGO", "TN": "TUN", "TR": "TUR", "TM": "TKM", "UG": "UGA", "AE": "ARE", "UZ": "UZB",
    "YE": "YEM",
}


@lru_cache(maxsize=1)
def member_countries():
    """IsDB member countries: [{iso3, iso2, name, bbox}], sorted by name."""
    from apps.reference.catalog import dataset_file
    path = dataset_file("member_countries")  # REFERENCE_DATA_DIR/catalog.json
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for f in data["features"]:
        iso2 = f["properties"]["iso"]
        xs, ys = [], []
        _collect(f["geometry"]["coordinates"], xs, ys)
        out.append({
            "iso3": ISO2_TO_ISO3[iso2],
            "iso2": iso2,
            "name": f["properties"]["name"],
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
        })
    return sorted(out, key=lambda c: c["name"])


def _collect(coords, xs, ys):
    if coords and isinstance(coords[0], (int, float)):
        xs.append(coords[0])
        ys.append(coords[1])
    else:
        for c in coords:
            _collect(c, xs, ys)


def country_by_iso3(iso3):
    return next((c for c in member_countries() if c["iso3"] == (iso3 or "").upper()), None)


def keys(pairs):
    return {k for k, _ in pairs}


def as_options(pairs):
    return [{"value": k, "label": v} for k, v in pairs]
