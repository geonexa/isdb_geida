"""
Charts for reports, as SVG: horizontal bars for tables that have a label column and a share (%) or area column
(land cover classes, slope classes, distance bands, suitability classes...). Colours come from the run's legend
when a row's label matches a legend entry.
"""
from html import escape

TEAL = "#0B3B47"
SHARE_KEYS = ("share", "share_pct", "percent", "pct")
VALUE_KEYS = ("area_km2", "km2", "km", "people", "population", "count")
MAX_ROWS = 14


def _fmt(v):
    if abs(v) >= 1000:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{v:.2f}".rstrip("0").rstrip(".")


def pick(table):
    """(label key, value key, unit) for a table worth charting, or None."""
    cols = table.get("columns") or []
    rows = table.get("rows") or []
    if not (2 <= len(rows) <= MAX_ROWS) or len(cols) < 2:
        return None
    label = cols[0]["key"]
    if not all(isinstance(r.get(label), str) for r in rows):
        return None
    for c in cols[1:]:
        if c["key"] in SHARE_KEYS or c.get("unit") == "%":
            return label, c["key"], "%"
    for c in cols[1:]:
        if c["key"] in VALUE_KEYS:
            return label, c["key"], c.get("unit") or ""
    return None


def bar_chart(table, colors=None):
    """SVG bars for a table (see pick), or None."""
    chosen = pick(table)
    if not chosen:
        return None
    label_key, value_key, unit = chosen
    rows = [(str(r.get(label_key)), r.get(value_key)) for r in table["rows"]]
    rows = [(lab, float(v)) for lab, v in rows if isinstance(v, (int, float))]
    if len(rows) < 2:
        return None
    colors = colors or {}
    top = max(v for _, v in rows) or 1
    row_h, gap, label_w, bar_w, value_w = 22, 6, 230, 330, 80
    width = label_w + bar_w + value_w
    height = len(rows) * (row_h + gap) + 4
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" role="img" '
           f'font-family="Outfit, sans-serif" font-size="12">']
    for i, (lab, v) in enumerate(rows):
        y = i * (row_h + gap) + 2
        w = max(1.5, bar_w * max(v, 0) / top)
        color = colors.get(lab) or TEAL
        short = lab if len(lab) <= 38 else lab[:36] + "…"
        out.append(f'<text x="{label_w - 8}" y="{y + row_h * 0.68:.1f}" text-anchor="end" fill="#2A2A2E">{escape(short)}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{w:.1f}" height="{row_h}" fill="{color}"/>')
        out.append(f'<text x="{label_w + w + 6:.1f}" y="{y + row_h * 0.68:.1f}" fill="#121114" font-weight="600">'
                   f'{_fmt(v)}{(" " + escape(unit)) if unit and unit != "%" else unit}</text>')
    out.append("</svg>")
    return "".join(out)


SERIES_COLORS = ["#0B3B47", "#C9A25B", "#2F8F4E", "#B5527A", "#2B7BB9", "#D9822B", "#5B5F97", "#3E7C7B", "#8C6D46",
                 "#7A9A01", "#A23B72", "#6C757D"]


def _nice_step(span, n=5):
    import math
    raw = span / n if span else 1
    p = 10 ** math.floor(math.log10(raw))
    return next(k * p for k in (1, 2, 2.5, 5, 10) if k * p >= raw)


def series_chart(chart):
    """SVG of a chart output (lines with gaps, or bars for one series), or None."""
    series = chart.get("series") or []
    xs = [p[0] for p in (series[0]["points"] if series else [])]
    vals = [p[1] for s in series for p in s["points"] if isinstance(p[1], (int, float))]
    if not xs or not vals:
        return None
    W, H, L, R, T, B = 720, 280, 60, 14, 14, 46
    lo, hi = min(0, min(vals)), max(vals)
    if hi == lo:
        hi = lo + 1
    step = _nice_step(hi - lo)
    lo, hi = (lo // step) * step, -(-hi // step) * step
    n = len(xs)
    xw = (W - L - R) / n
    x = lambda i: L + xw * (i + 0.5)                                    # noqa: E731
    y = lambda v: T + (H - T - B) * (1 - (v - lo) / (hi - lo))          # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="100%" role="img" '
           f'font-family="Outfit, sans-serif" font-size="11">']
    t = lo
    while t <= hi + step / 2:
        out.append(f'<line x1="{L}" x2="{W - R}" y1="{y(t):.1f}" y2="{y(t):.1f}" stroke="#E4E4E4"/>')
        out.append(f'<text x="{L - 6}" y="{y(t) + 4:.1f}" text-anchor="end" fill="#5C5C60">{_fmt(t)}</text>')
        t += step
    every = max(1, -(-n // 8))
    for i, lab in enumerate(xs):
        if i % every == 0:
            out.append(f'<text x="{x(i):.1f}" y="{H - B + 16}" text-anchor="middle" fill="#5C5C60">{escape(str(lab))}</text>')
    if chart.get("x_label"):
        out.append(f'<text x="{(L + W - R) / 2:.0f}" y="{H - 8}" text-anchor="middle" fill="#2A2A2E" font-weight="600">'
                   f'{escape(chart["x_label"])}</text>')
    if chart.get("kind") == "bar" and len(series) == 1:
        base = y(max(lo, 0))
        for i, (_, v) in enumerate(series[0]["points"]):
            if isinstance(v, (int, float)):
                out.append(f'<rect x="{x(i) - xw * 0.35:.1f}" y="{min(y(v), base):.1f}" width="{xw * 0.7:.1f}" '
                           f'height="{abs(y(v) - base):.1f}" fill="{SERIES_COLORS[0]}"/>')
    else:
        for k, s in enumerate(series):
            d, pen = "", False
            for i, (_, v) in enumerate(s["points"]):
                if not isinstance(v, (int, float)):
                    pen = False
                    continue
                d += f'{"L" if pen else "M"}{x(i):.1f} {y(v):.1f}'
                pen = True
            out.append(f'<path d="{d}" fill="none" stroke="{SERIES_COLORS[k % len(SERIES_COLORS)]}" stroke-width="2" '
                       f'stroke-linejoin="round" stroke-linecap="round"/>')
    out.append("</svg>")
    return "".join(out)


def series_legend(chart):
    """[{color, label, kind}] for a chart with several series (none for one)."""
    series = chart.get("series") or []
    if len(series) < 2:
        return []
    return [{"color": SERIES_COLORS[k % len(SERIES_COLORS)], "label": s["name"], "kind": "line"} for k, s in enumerate(series)]
