/**
 * Draws a layout as SVG, in millimetres (1 user unit = 1 mm). The same markup is
 * the editor's preview and every export: SVG as is, PNG/PDF/print rasterised from it.
 */
import type { MultiPolygon, Polygon } from "geojson";

import { projector, scaleOf, type BBox, type CapturedMap } from "@/features/print/capture";
import { DEFAULT_GLOBE, globeSvg, type World } from "@/features/print/globe";
import {
  fillVars, pageSize,
  type ColorbarItem, type Font, type Frame, type Item, type Layout, type LegendEntry, type LegendItem, type MapItem,
  type NorthItem, type OverviewItem, type PictureItem, type Ramp, type ScaleBarItem, type ShapeItem, type TextItem, type Vars,
} from "@/features/print/layout";

export type MapImage = { href: string; cap: CapturedMap };
export type Env = {
  vars: Vars;
  legend: LegendEntry[];
  ramp: Ramp | null;
  /** Captured map images by map/overview item id. */
  maps: Record<string, MapImage | undefined>;
  /** Image hrefs by picture src (data URLs for export). */
  pictures: Record<string, { href: string; w: number; h: number } | undefined>;
  /** @font-face rules embedded in exports. */
  fontCss?: string;
  /** Preview: show placeholders and hidden-text hints. */
  editing?: boolean;
  /** Map content being dragged in the editor: image shift in mm. */
  offsets?: Record<string, [number, number]>;
  /** World outlines and what to show on globe locators. */
  world?: World | null;
  globe?: { center: [number, number]; gid?: string; name?: string; marker?: [number, number] | null };
  /** Boundaries drawn on overview maps. */
  outlines?: { country?: Polygon | MultiPolygon; region?: Polygon | MultiPolygon };
};
export type Box = { x: number; y: number; w: number; h: number };

const PT = 0.3528; // mm per point
const FAMILY: Record<Font["family"], string> = {
  sans: "Outfit, 'Outfit Variable', 'Helvetica Neue', Arial, sans-serif",
  serif: "Georgia, 'Times New Roman', serif",
  mono: "'IBM Plex Mono', Menlo, Consolas, monospace",
};
export const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const n = (v: number) => (Math.round(v * 1000) / 1000).toString();

/* -------------------------------------------------------------- text */

let measureCtx: CanvasRenderingContext2D | null = null;
function measure(text: string, f: Font) {
  measureCtx ??= document.createElement("canvas").getContext("2d");
  if (!measureCtx) return text.length * f.size * PT * 0.5;
  measureCtx.font = `${f.italic ? "italic " : ""}${f.weight} ${f.size * PT * 20}px ${FAMILY[f.family]}`;
  return measureCtx.measureText(text).width / 20;
}

/** Wrap paragraphs to `maxW` mm. */
export function wrap(text: string, f: Font, maxW: number) {
  const out: string[] = [];
  for (const para of text.split("\n")) {
    if (!para.trim()) { out.push(""); continue; }
    let line = "";
    for (const word of para.split(/\s+/)) {
      const next = line ? `${line} ${word}` : word;
      if (line && measure(next, f) > maxW) { out.push(line); line = word; } else line = next;
    }
    out.push(line);
  }
  return out;
}

function fontAttrs(f: Font) {
  return `font-family="${esc(FAMILY[f.family])}" font-size="${n(f.size * PT)}" font-weight="${f.weight}"${f.italic ? ' font-style="italic"' : ""} fill="${f.color}"`;
}
const halo = (f: Font, on: boolean) => (on ? ` stroke="#ffffff" stroke-width="${n(f.size * PT * 0.28)}" stroke-linejoin="round" paint-order="stroke"` : "");

/** Lines of text at (x, top), aligned. */
function textLines(lines: string[], f: Font, x: number, top: number, anchor: "start" | "middle" | "end", lineH: number, withHalo = false) {
  const size = f.size * PT;
  return `<text ${fontAttrs(f)} text-anchor="${anchor}"${halo(f, withHalo)}>${lines.map((l, i) => `<tspan x="${n(x)}" y="${n(top + size * 0.8 + i * lineH)}">${esc(l) || " "}</tspan>`).join("")}</text>`;
}

/* -------------------------------------------------------------- frames */

function frameRect(b: Box, f: Frame) {
  if (!f.bg && !(f.stroke && f.strokeWidth > 0)) return "";
  const fill = f.bg ? `fill="${f.bg}" fill-opacity="${f.bgOpacity}"` : 'fill="none"';
  const stroke = f.stroke && f.strokeWidth > 0 ? ` stroke="${f.stroke}" stroke-width="${n(f.strokeWidth)}"` : "";
  return `<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" ${fill}${stroke}${f.shadow ? ' filter="url(#geida-shadow)"' : ""}/>`;
}
const inner = (it: Item): Box => ({ x: it.x + it.frame.padding, y: it.y + it.frame.padding, w: Math.max(1, it.w - 2 * it.frame.padding), h: Math.max(1, it.h - 2 * it.frame.padding) });

function placeholder(b: Box, label: string, env: Env) {
  if (!env.editing) return "";
  return `<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" fill="#eef1f3"/>`
    + `<text x="${n(b.x + b.w / 2)}" y="${n(b.y + b.h / 2)}" font-family="${esc(FAMILY.sans)}" font-size="${n(Math.min(4, b.h / 4))}" fill="#9aa3ab" text-anchor="middle" dominant-baseline="middle">${esc(label)}</text>`;
}

/* -------------------------------------------------------------- map + grid */

const INTERVALS = [0.0005, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10, 15, 20, 30, 45];
function gridInterval(span: number, wanted = 4) {
  return INTERVALS.find((c) => span / c <= wanted) ?? 45;
}
export function formatCoord(v: number, axis: "lon" | "lat", format: "dms" | "decimal", interval: number) {
  const hemi = axis === "lon" ? (v < 0 ? "W" : v > 0 ? "E" : "") : (v < 0 ? "S" : v > 0 ? "N" : "");
  const a = Math.abs(v);
  if (format === "decimal") {
    const dec = interval >= 1 ? 0 : Math.min(4, Math.ceil(-Math.log10(interval)));
    return `${a.toFixed(dec)}°${hemi}`;
  }
  let d = Math.floor(a), m = Math.round((a - d) * 60 * 100) / 100;
  if (m >= 60) { d += 1; m = 0; }
  const mi = Math.floor(m), s = Math.round((m - mi) * 60);
  if (interval >= 1 || (mi === 0 && s === 0)) return `${d}°${hemi}`;
  if (interval >= 1 / 60 || s === 0) return `${d}°${String(mi).padStart(2, "0")}′${hemi}`;
  return `${d}°${String(mi).padStart(2, "0")}′${String(s).padStart(2, "0")}″${hemi}`;
}

function renderMap(it: MapItem, env: Env, defs: string[]) {
  const b: Box = { x: it.x, y: it.y, w: it.w, h: it.h };
  const img = env.maps[it.id];
  const clip = `clip-${it.id}`;
  defs.push(`<clipPath id="${clip}"><rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}"/></clipPath>`);
  let out = it.frame.bg ? frameRect(b, { ...it.frame, stroke: "" }) : "";
  const [dx, dy] = env.offsets?.[it.id] ?? [0, 0];
  out += img
    ? `<g clip-path="url(#${clip})"><image href="${img.href}" x="${n(b.x + dx)}" y="${n(b.y + dy)}" width="${n(b.w)}" height="${n(b.h)}" preserveAspectRatio="none"/></g>`
    : placeholder(b, "Drawing map…", env);
  if (img && it.grid.show && !dx && !dy) out += renderGrid(it, img.cap.bounds, clip);
  if (it.frame.stroke && it.frame.strokeWidth > 0) out += `<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" fill="none" stroke="${it.frame.stroke}" stroke-width="${n(it.frame.strokeWidth)}"/>`;
  return out;
}

function renderGrid(it: MapItem, bounds: BBox, clip: string) {
  const g = it.grid;
  const p = projector(bounds, it.w, it.h);
  const [W, S, E, N] = bounds;
  const step = g.interval > 0 ? g.interval : gridInterval(Math.min(E - W, N - S));
  const lons: number[] = [], lats: number[] = [];
  for (let v = Math.ceil(W / step) * step; v <= E + 1e-9; v += step) lons.push(+v.toFixed(8));
  for (let v = Math.ceil(S / step) * step; v <= N + 1e-9; v += step) lats.push(+v.toFixed(8));
  if (lons.length > 60 || lats.length > 60) return "";
  const X = (lon: number) => it.x + p.x(lon), Y = (lat: number) => it.y + p.y(lat);
  const stroke = `stroke="${g.color}" stroke-width="${n(g.width)}"`;
  let lines = "";
  if (g.style === "lines") {
    lines += lons.map((v) => `<line x1="${n(X(v))}" y1="${n(it.y)}" x2="${n(X(v))}" y2="${n(it.y + it.h)}" ${stroke}/>`).join("");
    lines += lats.map((v) => `<line x1="${n(it.x)}" y1="${n(Y(v))}" x2="${n(it.x + it.w)}" y2="${n(Y(v))}" ${stroke}/>`).join("");
  } else {
    const c = 1.5;
    for (const lo of lons) for (const la of lats) {
      lines += `<path d="M${n(X(lo) - c)} ${n(Y(la))}H${n(X(lo) + c)}M${n(X(lo))} ${n(Y(la) - c)}V${n(Y(la) + c)}" ${stroke} fill="none"/>`;
    }
  }
  let out = `<g clip-path="url(#${clip})" stroke-opacity="0.8">${lines}</g>`;
  const f: Font = { family: "sans", size: g.labelSize, weight: 400, italic: false, color: "#1f2937" };
  const size = g.labelSize * PT;
  const lonLabel = (v: number) => formatCoord(v, "lon", g.format, step);
  const latLabel = (v: number) => formatCoord(v, "lat", g.format, step);
  const zebraW = g.labels === "outside" && g.zebra ? 1.2 : 0;

  if (zebraW) {
    // Alternating black/white bands between grid lines, on all four sides.
    const band = (vals: number[], pos: (v: number) => number, lo: number, hi: number, side: "h" | "v", at: number) => {
      const edges = [lo, ...vals.map(pos).filter((v) => v > lo && v < hi).sort((a, b) => a - b), hi];
      let s = "";
      for (let i = 0; i < edges.length - 1; i++) {
        const fill = i % 2 === 0 ? "#1f2937" : "#ffffff";
        s += side === "h"
          ? `<rect x="${n(edges[i])}" y="${n(at)}" width="${n(edges[i + 1] - edges[i])}" height="${zebraW}" fill="${fill}"/>`
          : `<rect x="${n(at)}" y="${n(edges[i])}" width="${zebraW}" height="${n(edges[i + 1] - edges[i])}" fill="${fill}"/>`;
      }
      return s;
    };
    out += band(lons, X, it.x, it.x + it.w, "h", it.y - zebraW) + band(lons, X, it.x, it.x + it.w, "h", it.y + it.h);
    out += band(lats, Y, it.y, it.y + it.h, "v", it.x - zebraW) + band(lats, Y, it.y, it.y + it.h, "v", it.x + it.w);
    out += `<rect x="${n(it.x - zebraW)}" y="${n(it.y - zebraW)}" width="${n(it.w + 2 * zebraW)}" height="${n(it.h + 2 * zebraW)}" fill="none" stroke="#1f2937" stroke-width="0.15"/>`;
  }
  if (g.labels === "outside") {
    const gap = zebraW + 0.8;
    const t = (x: number, y: number, s: string, anchor: string, rot = 0) =>
      `<text ${fontAttrs(f)} text-anchor="${anchor}" x="${n(x)}" y="${n(y)}"${rot ? ` transform="rotate(${rot} ${n(x)} ${n(y)})"` : ""}>${esc(s)}</text>`;
    for (const v of lons) {
      const x = X(v);
      if (x < it.x + size || x > it.x + it.w - size) continue;
      out += t(x, it.y - gap, lonLabel(v), "middle") + t(x, it.y + it.h + gap + size * 0.8, lonLabel(v), "middle");
    }
    for (const v of lats) {
      const y = Y(v);
      if (y < it.y + size || y > it.y + it.h - size) continue;
      out += t(it.x - gap, y, latLabel(v), "middle", -90) + t(it.x + it.w + gap + size * 0.8, y, latLabel(v), "middle", -90);
    }
  } else if (g.labels === "inside") {
    for (const v of lons) {
      const x = X(v);
      if (x < it.x + 6 || x > it.x + it.w - 6) continue;
      out += `<text ${fontAttrs(f)}${halo(f, true)} text-anchor="middle" x="${n(x)}" y="${n(it.y + 1 + size)}">${esc(lonLabel(v))}</text>`;
    }
    for (const v of lats) {
      const y = Y(v);
      if (y < it.y + 6 || y > it.y + it.h - 6) continue;
      out += `<text ${fontAttrs(f)}${halo(f, true)} text-anchor="start" x="${n(it.x + 1)}" y="${n(y - 0.6)}">${esc(latLabel(v))}</text>`;
    }
  }
  return out;
}

function renderOverview(it: OverviewItem, env: Env, items: Item[], defs: string[]) {
  const b: Box = { x: it.x, y: it.y, w: it.w, h: it.h };
  if (it.extent === "globe") {
    let out = env.world && env.globe
      ? globeSvg(b, it.id, { world: env.world, center: env.globe.center, highlight: { gid: env.globe.gid, name: env.globe.name },
          marker: env.globe.marker, style: { ...DEFAULT_GLOBE, ...it.globe }, markerColor: it.boxColor, lineWidth: it.outlineWidth ?? 0.35 })
      : placeholder(b, env.world === null ? "World outlines unavailable" : "Globe", env);
    if (it.frame.stroke && it.frame.strokeWidth > 0) out += `<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" fill="none" stroke="${it.frame.stroke}" stroke-width="${n(it.frame.strokeWidth)}"/>`;
    return out;
  }
  const img = env.maps[it.id];
  const clip = `clip-${it.id}`;
  defs.push(`<clipPath id="${clip}"><rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}"/></clipPath>`);
  let out = img
    ? `<image href="${img.href}" x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" preserveAspectRatio="none" clip-path="url(#${clip})"/>`
    : placeholder(b, "Overview", env);
  if (img && it.outline !== false) {
    const p = projector(img.cap.bounds, it.w, it.h);
    const color = it.outlineColor ?? "#0B3B47", width = it.outlineWidth ?? 0.35;
    const shapes = [env.outlines?.country, it.extent === "region" ? env.outlines?.region : undefined];
    shapes.forEach((g, i) => {
      if (!g) return;
      const d = outlinePath(g, (lon) => it.x + p.x(lon), (lat) => it.y + p.y(lat));
      // The region is the focus when shown; the country around it is drawn lighter.
      const w = i === 1 ? width : it.extent === "region" ? width * 0.7 : width;
      if (d) out += `<path d="${d}" fill="none" stroke="${color}" stroke-width="${n(w)}" stroke-linejoin="round"${i === 0 && it.extent === "region" ? ' stroke-opacity="0.6"' : ""} clip-path="url(#${clip})"/>`;
    });
  }
  const main = env.maps[it.mapId];
  if (img && main && items.some((x) => x.id === it.mapId)) {
    const p = projector(img.cap.bounds, it.w, it.h);
    const [w, s, e, nn] = main.cap.bounds;
    const x1 = it.x + p.x(w), x2 = it.x + p.x(e), y1 = it.y + p.y(nn), y2 = it.y + p.y(s);
    const bw = x2 - x1, bh = y2 - y1;
    if (bw < 2.5 && bh < 2.5) {
      const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2;
      out += `<g clip-path="url(#${clip})"><circle cx="${n(cx)}" cy="${n(cy)}" r="1.6" fill="${it.boxColor}" fill-opacity="0.25" stroke="${it.boxColor}" stroke-width="${n(it.boxWidth)}"/><circle cx="${n(cx)}" cy="${n(cy)}" r="0.5" fill="${it.boxColor}"/></g>`;
    } else {
      out += `<rect x="${n(x1)}" y="${n(y1)}" width="${n(bw)}" height="${n(bh)}" fill="${it.boxColor}" fill-opacity="0.12" stroke="${it.boxColor}" stroke-width="${n(it.boxWidth)}" clip-path="url(#${clip})"/>`;
    }
  }
  if (it.frame.stroke && it.frame.strokeWidth > 0) out += `<rect x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" fill="none" stroke="${it.frame.stroke}" stroke-width="${n(it.frame.strokeWidth)}"/>`;
  return out;
}

/** SVG path for polygon rings, dropping points closer than 0.15 mm to the last one kept. */
function outlinePath(g: Polygon | MultiPolygon, X: (lon: number) => number, Y: (lat: number) => number) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  let d = "";
  for (const poly of polys) for (const ring of poly) {
    let lx = NaN, ly = NaN, part = "", kept = 0;
    for (const [lon, lat] of ring) {
      const x = X(lon), y = Y(lat);
      if (kept && Math.abs(x - lx) < 0.15 && Math.abs(y - ly) < 0.15) continue;
      part += `${kept ? "L" : "M"}${n(x)} ${n(y)}`;
      lx = x; ly = y; kept++;
    }
    if (kept > 2) d += part + "Z";
  }
  return d;
}

/* -------------------------------------------------------------- text, picture, shape */

function renderText(it: TextItem, env: Env) {
  const b = inner(it);
  const lines = wrap(fillVars(it.text, env.vars), it.font, b.w);
  const lineH = it.font.size * PT * it.lineHeight;
  const blockH = lines.length * lineH - (lineH - it.font.size * PT);
  const top = it.valign === "top" ? b.y : it.valign === "middle" ? b.y + (b.h - blockH) / 2 : b.y + b.h - blockH;
  const x = it.align === "left" ? b.x : it.align === "center" ? b.x + b.w / 2 : b.x + b.w;
  const anchor = it.align === "left" ? "start" : it.align === "center" ? "middle" : "end";
  return frameRect(it, it.frame) + textLines(lines, it.font, x, top, anchor, lineH, it.halo);
}

function renderPicture(it: PictureItem, env: Env) {
  const b = inner(it);
  const pic = env.pictures[it.src];
  if (!pic) return frameRect(it, it.frame) + placeholder(b, "Picture", env);
  const par = it.fit === "cover" ? "xMidYMid slice" : "xMidYMid meet";
  return frameRect(it, it.frame) + `<image href="${pic.href}" x="${n(b.x)}" y="${n(b.y)}" width="${n(b.w)}" height="${n(b.h)}" preserveAspectRatio="${par}"/>`;
}

function renderShape(it: ShapeItem) {
  const stroke = it.stroke && it.strokeWidth > 0 ? `stroke="${it.stroke}" stroke-width="${n(it.strokeWidth)}"` : 'stroke="none"';
  const fill = it.fill && it.fillOpacity > 0 ? `fill="${it.fill}" fill-opacity="${it.fillOpacity}"` : 'fill="none"';
  if (it.shape === "line") return `<line x1="${n(it.x)}" y1="${n(it.y)}" x2="${n(it.x + it.w)}" y2="${n(it.y + it.h)}" ${stroke} stroke-linecap="round"/>`;
  if (it.shape === "ellipse") return `<ellipse cx="${n(it.x + it.w / 2)}" cy="${n(it.y + it.h / 2)}" rx="${n(it.w / 2)}" ry="${n(it.h / 2)}" ${fill} ${stroke}/>`;
  return `<rect x="${n(it.x)}" y="${n(it.y)}" width="${n(it.w)}" height="${n(it.h)}" ${fill} ${stroke}/>`;
}

/* -------------------------------------------------------------- north arrow */

function renderNorth(it: NorthItem) {
  const b = inner(it);
  // Drawn in a 10 x 14 box, scaled to fit.
  const k = Math.min(b.w / 10, b.h / 14);
  const ox = b.x + (b.w - 10 * k) / 2, oy = b.y + (b.h - 14 * k) / 2;
  const c = it.color;
  const g = (body: string) => `<g transform="translate(${n(ox)} ${n(oy)}) scale(${n(k)})">${body}</g>`;
  const N = `<text x="5" y="3.4" font-family="${esc(FAMILY.sans)}" font-size="3.6" font-weight="700" fill="${c}" text-anchor="middle">N</text>`;
  let body = "";
  if (it.style === "arrow") body = `${N}<path d="M5 4.4 L8.2 13.6 L5 11.4 Z" fill="#ffffff" stroke="${c}" stroke-width="0.35" stroke-linejoin="round"/><path d="M5 4.4 L1.8 13.6 L5 11.4 Z" fill="${c}" stroke="${c}" stroke-width="0.35" stroke-linejoin="round"/>`;
  else if (it.style === "simple") body = `${N}<path d="M5 4.6 L8 13.4 L2 13.4 Z" fill="${c}"/>`;
  else body = `${N}<g transform="translate(5 9.2)"><path d="M0 -4.6 L1 -1 L0 0 Z M0 4.6 L-1 1 L0 0 Z M4.6 0 L1 1 L0 0 Z M-4.6 0 L-1 -1 L0 0 Z" fill="${c}"/><path d="M0 -4.6 L-1 -1 L0 0 Z M0 4.6 L1 1 L0 0 Z M4.6 0 L1 -1 L0 0 Z M-4.6 0 L-1 1 L0 0 Z" fill="#ffffff" stroke="${c}" stroke-width="0.2"/><circle r="0.5" fill="${c}"/></g>`;
  return frameRect(it, it.frame) + g(body);
}

/* -------------------------------------------------------------- scale bar */

const UNIT_M = { km: 1000, m: 1, mi: 1609.344 } as const;
function niceBelow(v: number) {
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [5, 2.5, 2, 1]) if (m * p <= v) return m * p;
  return p;
}
const fmtNum = (v: number) => (Math.abs(v) >= 100 || Number.isInteger(v) ? Math.round(v).toLocaleString("en") : v.toLocaleString("en", { maximumFractionDigits: 2 }));

/** 1:N to three significant figures (1:1,012,076 -> 1:1,010,000), as printed scales usually are. */
export function roundScale(v: number) {
  if (v <= 0) return 0;
  const p = 10 ** Math.max(0, Math.floor(Math.log10(v)) - 2);
  return Math.round(v / p) * p;
}

export function scaleOfMapItem(map: MapItem, env: Env) {
  const img = env.maps[map.id];
  return img ? scaleOf(img.cap, map.w) : 0;
}

function renderScaleBar(it: ScaleBarItem, env: Env, items: Item[]) {
  const b = inner(it);
  const map = items.find((x) => x.id === it.mapId && x.type === "map") as MapItem | undefined;
  const img = map && env.maps[map.id];
  if (!map || !img) return frameRect(it, it.frame) + placeholder(b, map ? "Scale bar" : "Scale bar: pick a map", env);
  const metersPerMm = (img.cap.metersPerPixel * img.cap.image.width) / map.w;
  const size = it.font.size * PT;
  const unitLabel0 = it.units;
  const reserve = measure(` ${unitLabel0}`, it.font) + 1;
  const avail = b.w - reserve - 1;
  let unit: "km" | "m" | "mi" = it.units;
  let total = niceBelow((avail * metersPerMm) / UNIT_M[unit]);
  if (unit === "km" && total < 1) { unit = "m"; total = niceBelow((avail * metersPerMm) / UNIT_M.m); }
  const len = (total * UNIT_M[unit]) / metersPerMm;
  const segs = Math.max(1, Math.min(10, it.segments));
  const segL = len / segs;
  const x0 = b.x + 0.5;
  const ratioH = it.showRatio ? size * 1.5 : 0;
  const barY = b.y + Math.max(0, (b.h - (it.barHeight + size * 1.6 + ratioH)) / 2);
  const bh = it.barHeight;
  const c = it.color;
  let bar = "";
  if (it.style === "line") {
    bar += `<line x1="${n(x0)}" y1="${n(barY + bh)}" x2="${n(x0 + len)}" y2="${n(barY + bh)}" stroke="${c}" stroke-width="0.35"/>`;
    for (let i = 0; i <= segs; i++) bar += `<line x1="${n(x0 + i * segL)}" y1="${n(barY + (i === 0 || i === segs ? 0 : bh * 0.45))}" x2="${n(x0 + i * segL)}" y2="${n(barY + bh)}" stroke="${c}" stroke-width="0.3"/>`;
  } else {
    for (let i = 0; i < segs; i++) {
      const fill = it.style === "hollow" ? "#ffffff" : i % 2 === 0 ? c : "#ffffff";
      if (it.style === "double") {
        bar += `<rect x="${n(x0 + i * segL)}" y="${n(barY)}" width="${n(segL)}" height="${n(bh / 2)}" fill="${i % 2 === 0 ? c : "#ffffff"}"/>`;
        bar += `<rect x="${n(x0 + i * segL)}" y="${n(barY + bh / 2)}" width="${n(segL)}" height="${n(bh / 2)}" fill="${i % 2 === 0 ? "#ffffff" : c}"/>`;
      } else {
        bar += `<rect x="${n(x0 + i * segL)}" y="${n(barY)}" width="${n(segL)}" height="${n(bh)}" fill="${fill}"${it.style === "hollow" ? ` stroke="${c}" stroke-width="0.25"` : ""}/>`;
      }
    }
    bar += `<rect x="${n(x0)}" y="${n(barY)}" width="${n(len)}" height="${n(bh)}" fill="none" stroke="${c}" stroke-width="0.3"/>`;
  }
  const ly = barY + bh + 0.8;
  const labelAt = (i: number) => {
    const v = (total / segs) * i;
    const x = x0 + i * segL;
    const last = i === segs;
    return `<text ${fontAttrs({ ...it.font, color: c })} text-anchor="middle" x="${n(x)}" y="${n(ly + size * 0.8)}">${esc(fmtNum(v))}</text>`
      + (last ? `<text ${fontAttrs({ ...it.font, color: c })} text-anchor="start" x="${n(x + measure(fmtNum(v), it.font) / 2 + 0.8)}" y="${n(ly + size * 0.8)}">${unit}</text>` : "");
  };
  const step = segs > 5 ? 2 : 1;
  let labels = "";
  for (let i = 0; i <= segs; i++) if (i % step === 0 || i === segs) labels += labelAt(i);
  if (it.showRatio) {
    labels += `<text ${fontAttrs({ ...it.font, color: c })} text-anchor="start" x="${n(x0)}" y="${n(ly + size * 1.6 + size * 0.85)}">Scale 1:${roundScale(scaleOf(img.cap, map.w)).toLocaleString("en")}</text>`;
  }
  return frameRect(it, it.frame) + bar + labels;
}

/* -------------------------------------------------------------- colour bar */

function renderColorbar(it: ColorbarItem, env: Env, defs: string[]) {
  const b = inner(it);
  const r = env.ramp;
  if (!r) return frameRect(it, it.frame) + placeholder(b, "Colour bar: no continuous layer on the map", env);
  const size = it.font.size * PT;
  const gid = `ramp-${it.id}`;
  const vertical = it.orientation === "vertical";
  defs.push(`<linearGradient id="${gid}" x1="0" y1="${vertical ? 1 : 0}" x2="${vertical ? 0 : 1}" y2="0">${r.colors.map((c, i) => `<stop offset="${n(i / Math.max(1, r.colors.length - 1))}" stop-color="${c}"/>`).join("")}</linearGradient>`);
  const ticks = Math.max(2, it.ticks);
  const vals = Array.from({ length: ticks }, (_, i) => r.min + ((r.max - r.min) * i) / (ticks - 1));
  const f = it.font;
  let out = frameRect(it, it.frame);
  const label = fillVars(it.label, env.vars);
  if (!vertical) {
    const top = label ? b.y + size * 1.4 : b.y;
    const barH = Math.max(1.5, Math.min(4, b.h - (top - b.y) - size * 1.8));
    if (label) out += `<text ${fontAttrs({ ...f, weight: 600 })} x="${n(b.x)}" y="${n(b.y + size * 0.85)}">${esc(label)}</text>`;
    out += `<rect x="${n(b.x)}" y="${n(top)}" width="${n(b.w)}" height="${n(barH)}" fill="url(#${gid})" stroke="#6b7280" stroke-width="0.15"/>`;
    vals.forEach((v, i) => {
      const x = b.x + (b.w * i) / (ticks - 1);
      const anchor = i === 0 ? "start" : i === ticks - 1 ? "end" : "middle";
      out += `<line x1="${n(x)}" y1="${n(top + barH)}" x2="${n(x)}" y2="${n(top + barH + 0.8)}" stroke="#6b7280" stroke-width="0.15"/>`;
      out += `<text ${fontAttrs(f)} text-anchor="${anchor}" x="${n(x)}" y="${n(top + barH + 0.9 + size * 0.85)}">${esc(fmtNum(v))}</text>`;
    });
  } else {
    const top = label ? b.y + size * 1.6 : b.y;
    const barW = Math.min(4, b.w * 0.25);
    const barH = b.h - (top - b.y);
    if (label) out += `<text ${fontAttrs({ ...f, weight: 600 })} x="${n(b.x)}" y="${n(b.y + size * 0.85)}">${esc(label)}</text>`;
    out += `<rect x="${n(b.x)}" y="${n(top)}" width="${n(barW)}" height="${n(barH)}" fill="url(#${gid})" stroke="#6b7280" stroke-width="0.15"/>`;
    vals.forEach((v, i) => {
      const y = top + barH - (barH * i) / (ticks - 1);
      out += `<line x1="${n(b.x + barW)}" y1="${n(y)}" x2="${n(b.x + barW + 0.8)}" y2="${n(y)}" stroke="#6b7280" stroke-width="0.15"/>`;
      out += `<text ${fontAttrs(f)} x="${n(b.x + barW + 1.4)}" y="${n(y + size * 0.35)}">${esc(fmtNum(v))}</text>`;
    });
  }
  return out;
}

/* -------------------------------------------------------------- legend */

type Row = { kind: "head" | "item"; text: string; swatch?: { color: string; size?: number; area?: boolean } };

function legendRows(it: LegendItem, legend: LegendEntry[]): Row[] {
  const rows: Row[] = [];
  for (const e of legend) {
    const edit = it.edits[e.id];
    if (edit?.hidden) continue;
    const name = edit?.name || e.name;
    const area = e.id === "area";
    if (e.swatches.length > 1 || e.swatches.some((s) => s.label)) {
      rows.push({ kind: "head", text: name });
      for (const s of e.swatches) rows.push({ kind: "item", text: s.label ?? "", swatch: { color: s.color, size: s.size } });
    } else {
      rows.push({ kind: "item", text: name, swatch: { color: e.swatches[0]?.color ?? "#999", size: e.swatches[0]?.size, area } });
    }
  }
  return rows;
}

/** The legend drawn, and the box it needs when it sizes itself. */
function renderLegend(it: LegendItem, env: Env): { svg: string; box: Box } {
  const rows = legendRows(it, env.legend);
  const pad = it.frame.padding;
  const tSize = it.titleFont.size * PT, lSize = it.labelFont.size * PT;
  const rowH = Math.max(it.symbolH, lSize * 1.25) + 1.1;
  const title = fillVars(it.title, env.vars).trim();
  const titleH = title ? tSize * 1.6 : 0;
  const cols = Math.max(1, Math.min(4, it.columns));
  const perCol = Math.max(1, Math.ceil(rows.length / cols));
  const colRows = Array.from({ length: cols }, (_, c) => rows.slice(c * perCol, (c + 1) * perCol)).filter((r) => r.length);
  const headFont: Font = { ...it.labelFont, weight: 600 };
  const colW = colRows.map((cr) => Math.max(...cr.map((r) => (r.kind === "head" ? measure(r.text, headFont) : it.symbolW + 1.8 + measure(r.text, it.labelFont)))));
  const gap = 4;
  const contentW = Math.max(title ? measure(title, it.titleFont) : 0, colW.reduce((a, b) => a + b, 0) + gap * (colW.length - 1));
  const contentH = titleH + perCol * rowH - 1.1;
  const box: Box = it.auto
    ? { x: it.x, y: it.y, w: Math.max(10, contentW + 2 * pad + 0.5), h: Math.max(6, (rows.length ? contentH : lSize * 2) + 2 * pad) }
    : { x: it.x, y: it.y, w: it.w, h: it.h };
  let out = frameRect(box, it.frame);
  const x0 = box.x + pad, y0 = box.y + pad;
  if (title) out += `<text ${fontAttrs(it.titleFont)} x="${n(x0)}" y="${n(y0 + tSize * 0.85)}">${esc(title)}</text>`;
  if (!rows.length && env.editing) out += `<text ${fontAttrs({ ...it.labelFont, color: "#9aa3ab" })} x="${n(x0)}" y="${n(y0 + titleH + lSize)}">No layers on the map</text>`;
  let cx = x0;
  colRows.forEach((cr, ci) => {
    cr.forEach((r, ri) => {
      const ry = y0 + titleH + ri * rowH;
      const mid = ry + Math.max(it.symbolH, lSize * 1.25) / 2;
      if (r.kind === "head") {
        out += `<text ${fontAttrs(headFont)} x="${n(cx)}" y="${n(mid + lSize * 0.35)}">${esc(r.text)}</text>`;
        return;
      }
      const sw = r.swatch!;
      const sy = mid - it.symbolH / 2;
      if (sw.size) {
        const rad = Math.min(it.symbolH / 2, Math.max(0.8, sw.size * 0.28));
        out += `<circle cx="${n(cx + it.symbolW / 2)}" cy="${n(mid)}" r="${n(rad)}" fill="${sw.color}" stroke="#ffffff" stroke-width="0.25"/>`;
      } else if (sw.area) {
        out += `<rect x="${n(cx)}" y="${n(sy)}" width="${n(it.symbolW)}" height="${n(it.symbolH)}" fill="${sw.color}" fill-opacity="0.18" stroke="${sw.color}" stroke-width="0.45"/>`;
      } else {
        out += `<rect x="${n(cx)}" y="${n(sy)}" width="${n(it.symbolW)}" height="${n(it.symbolH)}" fill="${sw.color}" stroke="#6b7280" stroke-width="0.12"/>`;
      }
      out += `<text ${fontAttrs(it.labelFont)} x="${n(cx + it.symbolW + 1.8)}" y="${n(mid + lSize * 0.35)}">${esc(r.text)}</text>`;
    });
    cx += colW[ci] + gap;
  });
  return { svg: out, box };
}

/* -------------------------------------------------------------- page */

export type Rendered = { body: string; defs: string; boxes: Record<string, Box>; width: number; height: number };

export function renderLayout(layout: Layout, env: Env): Rendered {
  const { w: W, h: H } = pageSize(layout.page);
  const defs: string[] = [
    `<filter id="geida-shadow" x="-10%" y="-10%" width="130%" height="130%"><feDropShadow dx="0.3" dy="0.5" stdDeviation="0.6" flood-color="#000" flood-opacity="0.18"/></filter>`,
  ];
  const boxes: Record<string, Box> = {};
  let body = `<rect x="0" y="0" width="${n(W)}" height="${n(H)}" fill="${layout.page.background}"/>`;
  for (const it of layout.items) {
    boxes[it.id] = { x: it.x, y: it.y, w: it.w, h: it.h };
    if (!it.visible) continue;
    let svg = "";
    switch (it.type) {
      case "map": svg = renderMap(it, env, defs); break;
      case "overview": svg = renderOverview(it, env, layout.items, defs); break;
      case "text": svg = renderText(it, env); break;
      case "picture": svg = renderPicture(it, env); break;
      case "shape": svg = renderShape(it); break;
      case "north": svg = renderNorth(it); break;
      case "scalebar": svg = renderScaleBar(it, env, layout.items); break;
      case "colorbar": svg = renderColorbar(it, env, defs); break;
      case "legend": { const r = renderLegend(it, env); svg = r.svg; boxes[it.id] = r.box; break; }
    }
    body += `<g data-item="${it.id}">${svg}</g>`;
  }
  const bd = layout.page.border;
  if (bd.show) {
    const i = layout.page.margin / 2;
    body += `<rect x="${n(i)}" y="${n(i)}" width="${n(W - 2 * i)}" height="${n(H - 2 * i)}" fill="none" stroke="${bd.color}" stroke-width="${n(bd.width)}"/>`;
  }
  return { body, defs: defs.join(""), boxes, width: W, height: H };
}

/** A standalone SVG document (page size in mm). */
export function svgDocument(r: Rendered, fontCss = "") {
  return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="${n(r.width)}mm" height="${n(r.height)}mm" viewBox="0 0 ${n(r.width)} ${n(r.height)}">`
    + `<defs>${fontCss ? `<style>${fontCss}</style>` : ""}${r.defs}</defs>${r.body}</svg>`;
}
