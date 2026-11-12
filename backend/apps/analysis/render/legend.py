"""
Legends for raster outputs: how values become colours on the map, and the legend shown with them.

A legend is a dict (or a YAML file next to the analysis, e.g. legend.yaml):

    type: ramp                      # continuous values
    palette: ["#FFFFCC", "#FD8D3C", "#800026"]
    min: 0
    max: 30
    unit: degrees

    type: classes                   # classified values
    items:
      - {value: 1, color: "#1A9850", label: "Flat (0–2°)"}
      - {value: 2, color: "#FEE08B", label: "Gentle (2–5°)"}

ramp() builds a ramp from the data itself when an analysis gives no legend.
"""
from pathlib import Path

import numpy as np
import yaml

VIRIDIS = ["#440154", "#3B528B", "#21918C", "#5EC962", "#FDE725"]


def load(spec, folder=None):
    """A legend from a dict, or from a YAML file name relative to the analysis folder."""
    if isinstance(spec, (str, Path)):
        path = Path(folder or ".") / spec
        if not path.exists():
            raise ValueError(f"Legend file {path} is missing.")
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(spec, dict) or spec.get("type") not in ("ramp", "classes"):
        raise ValueError("A legend needs type: ramp (palette, min, max) or type: classes (items).")
    if spec["type"] == "ramp" and (len(spec.get("palette") or []) < 2 or spec.get("min") is None or spec.get("max") is None):
        raise ValueError("A ramp legend needs a palette of two or more colours, min and max.")
    if spec["type"] == "classes" and not spec.get("items"):
        raise ValueError("A classes legend needs items: [{value, color, label}].")
    return spec


def ramp(data, palette=None, unit="", low=2, high=98):
    """A ramp legend stretched over the data's 2nd–98th percentile."""
    vals = data[np.isfinite(data)]
    lo, hi = (float(np.percentile(vals, low)), float(np.percentile(vals, high))) if vals.size else (0.0, 1.0)
    if hi <= lo:
        hi = lo + 1
    # Values above the 98th percentile take the last colour: say so in the legend.
    return {"type": "ramp", "palette": palette or VIRIDIS, "min": _nice(lo), "max": _nice(hi), "unit": unit,
            "open_max": bool(vals.size and float(vals.max()) > hi)}


def _nice(v):
    return round(v) if abs(v) >= 100 else round(v, 2)


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def colorize(data, spec, inside=None, alpha=220):
    """RGBA uint8 image of data (NaN and pixels outside `inside` are transparent)."""
    rgba = np.zeros(data.shape + (4,), dtype=np.uint8)
    valid = np.isfinite(data) if inside is None else np.isfinite(data) & inside
    if spec["type"] == "classes":
        for item in spec["items"]:
            m = valid & (data == item["value"])
            rgba[m] = (*_rgb(item["color"]), alpha)
        return rgba
    stops = np.array([_rgb(c) for c in spec["palette"]], dtype="float64")
    lo, hi = float(spec["min"]), float(spec["max"])
    t = np.clip((data - lo) / ((hi - lo) or 1), 0, 1) * (len(stops) - 1)
    t = np.where(valid, t, 0)
    k = np.minimum(np.floor(t).astype(int), len(stops) - 2)
    f = (t - k)[..., None]
    rgb = stops[k] + (stops[k + 1] - stops[k]) * f
    rgba[valid, :3] = np.round(rgb[valid]).astype(np.uint8)
    rgba[valid, 3] = alpha
    return rgba


def _fmt(v):
    n = _nice(v)
    return f"{int(n):,}" if float(n).is_integer() else f"{n:,}"


def _readable_step(span, n):
    """The readable step (1, 2, 2.5 or 5 × a power of ten) nearest to span / n."""
    raw = span / max(n, 1)
    if raw <= 0:
        return 1.0
    mag = 10 ** np.floor(np.log10(raw))
    return float(min((k * mag for k in (1, 2, 2.5, 5, 10)), key=lambda v: abs(v - raw)))


def color_at(spec, value):
    """The ramp colour of a value, as #RRGGBB."""
    rgba = colorize(np.array([[value]], dtype="float64"), spec)
    return "#%02X%02X%02X" % tuple(int(c) for c in rgba[0, 0, :3])


def items(spec, ranges=None):
    """
    Legend rows for the map and reports: [{label, color}].
    classes: one row per class. ramp: value ranges with readable bounds (about one per palette
    colour, or `ranges`), each with the ramp colour at its middle; the first and last ranges
    end at the legend's min and max, and "open_max: true" adds a last "max and above" row
    (values beyond max take the last colour); "open_min: true" a first "below min" row.
    """
    if spec["type"] == "classes":
        return [{"label": i["label"], "color": i["color"]} for i in spec["items"]]
    unit = f" {spec['unit']}" if spec.get("unit") else ""
    lo, hi = float(spec["min"]), float(spec["max"])
    step = _readable_step(hi - lo, ranges or len(spec["palette"]))
    edges = [lo]
    v = (np.floor(lo / step) + 1) * step
    while v < hi - step * 1e-6:
        edges.append(float(v))
        v += step
    edges.append(hi)
    rows = [{"label": f"{_fmt(a)}–{_fmt(b)}{unit}", "color": color_at(spec, (a + b) / 2)}
            for a, b in zip(edges[:-1], edges[1:])]
    if spec.get("open_min"):
        rows.insert(0, {"label": f"below {_fmt(lo)}{unit}", "color": color_at(spec, lo)})
    if spec.get("open_max"):
        rows.append({"label": f"{_fmt(hi)}{unit} and above", "color": color_at(spec, hi)})
    return rows
