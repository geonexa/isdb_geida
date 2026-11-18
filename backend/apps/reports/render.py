"""
One template, two outputs: the report HTML (Django template + report.css) is the web report as it is, and
WeasyPrint prints the same HTML to PDF (A4, running header and footer, page numbers, contents with page
numbers). Fonts and logos are embedded, so the HTML file stands alone.
"""
import base64
from functools import lru_cache
from pathlib import Path

from django.template.loader import render_to_string

STATIC = Path(__file__).resolve().parent / "static" / "reports"


@lru_cache(maxsize=None)
def _data_uri(name, mime):
    return f"data:{mime};base64,{base64.b64encode((STATIC / name).read_bytes()).decode()}"


@lru_cache(maxsize=None)
def _css():
    fonts = "".join(
        f"@font-face{{font-family:'Outfit';src:url({_data_uri('fonts/' + f, 'font/woff2')}) format('woff2');"
        f"font-weight:100 900;font-style:normal;unicode-range:{r}}}"
        for f, r in (("outfit-latin-wght-normal.woff2",
                      "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,"
                      "U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"),
                     ("outfit-latin-ext-wght-normal.woff2",
                      "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,"
                      "U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,"
                      "U+A720-A7FF")))
    return fonts + (STATIC / "report.css").read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def _map_assets():
    """Leaflet (BSD-2) and the report's map script, embedded so the web report works on its own."""
    js = (STATIC / "vendor/leaflet/leaflet.js").read_text(encoding="utf-8")
    js = js.split("//# sourceMappingURL")[0]
    css = (STATIC / "vendor/leaflet/leaflet.css").read_text(encoding="utf-8")
    return css, js + "\n" + (STATIC / "imap.js").read_text(encoding="utf-8")


def _web_maps(context):
    """{"base": basemaps and area, "maps": {figure number: layer}} for the interactive maps."""
    maps = {}
    for sec in context.get("sections") or []:
        for mp in sec.get("maps") or []:
            if mp.get("web"):
                maps[str(mp["no"])] = mp["web"]
    return {"base": context.get("web_maps") or {}, "maps": maps}


def render_html(context, mode="web", pdf_url="", status=""):
    """The report page. mode: "web" (screen layout with a contents bar) or "pdf" (what WeasyPrint prints)."""
    extra = {}
    if mode == "web" and context.get("web_maps"):
        css, js = _map_assets()
        extra = {"map_css": css, "map_js": js, "imaps": _web_maps(context)}
    return render_to_string("reports/report.html", {
        **context, **extra, "mode": mode, "pdf_url": pdf_url, "status": status, "css": _css(),
        "isdb_logo": _data_uri("img/isdb-logo.png", "image/png"),
        "geida_logo": _data_uri("img/geida-logo.png", "image/png"),
    })


def write_pdf(context, path):
    """Print the report to PDF. Returns the number of pages."""
    from weasyprint import HTML
    doc = HTML(string=render_html(context, mode="pdf"), base_url=str(STATIC)).render()
    path = Path(path)
    tmp = path.with_suffix(".part")
    doc.write_pdf(tmp, pdf_variant="pdf/ua-1", uncompressed_pdf=False)
    tmp.replace(path)
    return len(doc.pages)
