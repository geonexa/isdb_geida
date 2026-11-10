/**
 * Globe locator for overview maps: an orthographic globe centred on the project's
 * country, the country highlighted, neighbours in grey, a graticule and a marker for
 * the project area. Drawn as SVG vectors from GEIDA's simplified world outlines
 * (`/api/boundaries/world/`), so it stays sharp at any print size.
 */
import type { MultiPolygon, Polygon } from "geojson";

import { api } from "@/shared/api/client";

export type WorldFeature = { properties: { gid: string; name: string }; geometry: Polygon | MultiPolygon };
export type World = { features: WorldFeature[] };

let world: Promise<World> | null = null;
/** World outlines, fetched once per page load. */
export function loadWorld(): Promise<World> {
  world ??= api<World>("/api/boundaries/world/").catch((e) => { world = null; throw e; });
  return world;
}

export type GlobeStyle = { ocean: string; land: string; border: string; highlight: string; graticule: boolean; marker?: boolean };
export const DEFAULT_GLOBE: GlobeStyle = { ocean: "#ffffff", land: "#e5e7eb", border: "#9ca3af", highlight: "#0B3B47", graticule: true, marker: true };

const RAD = Math.PI / 180;
const n = (v: number) => (Math.round(v * 1000) / 1000).toString();

/**
 * Orthographic projection centred on lon0/lat0 for a globe of radius r at cx/cy.
 * Points on the far side are pushed to the horizon, so polygons that cross it close
 * along the rim instead of jumping across the globe.
 */
function projector(lon0: number, lat0: number, cx: number, cy: number, r: number) {
  const s0 = Math.sin(lat0 * RAD), c0 = Math.cos(lat0 * RAD);
  return (lon: number, lat: number): [number, number, boolean] => {
    const l = (lon - lon0) * RAD, p = lat * RAD;
    const cp = Math.cos(p), sp = Math.sin(p), cl = Math.cos(l);
    const x = cp * Math.sin(l);
    const y = c0 * sp - s0 * cp * cl;
    const visible = s0 * sp + c0 * cp * cl >= 0;
    if (visible) return [cx + r * x, cy - r * y, true];
    const len = Math.hypot(x, y) || 1;
    return [cx + (r * x) / len, cy - (r * y) / len, false];
  };
}

/** SVG path for polygon rings; null when no point of the shape faces the viewer. */
function shapePath(g: Polygon | MultiPolygon, proj: ReturnType<typeof projector>) {
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  let d = "", seen = false;
  for (const poly of polys) for (const ring of poly) {
    let part = "", lastX = NaN, lastY = NaN, k = 0;
    for (const [lon, lat] of ring) {
      const [x, y, vis] = proj(lon, lat);
      seen ||= vis;
      if (k && Math.abs(x - lastX) < 0.08 && Math.abs(y - lastY) < 0.08) continue;
      part += `${k ? "L" : "M"}${n(x)} ${n(y)}`;
      lastX = x; lastY = y; k++;
    }
    if (k > 2) d += part + "Z";
  }
  return seen ? d : null;
}

/** Meridians and parallels every 30°, visible parts only. */
function graticulePath(proj: ReturnType<typeof projector>) {
  let d = "";
  const line = (pts: [number, number][]) => {
    let pen = false;
    for (const [lon, lat] of pts) {
      const [x, y, vis] = proj(lon, lat);
      if (!vis) { pen = false; continue; }
      d += `${pen ? "L" : "M"}${n(x)} ${n(y)}`;
      pen = true;
    }
  };
  for (let lon = -180; lon < 180; lon += 30) line(Array.from({ length: 61 }, (_, i) => [lon, -90 + i * 3] as [number, number]));
  for (let lat = -60; lat <= 60; lat += 30) line(Array.from({ length: 121 }, (_, i) => [-180 + i * 3, lat] as [number, number]));
  return d;
}

/**
 * The globe as SVG in a box (mm). `highlight` matches a world feature by GADM id
 * (= ISO3 for countries) or, failing that, by name.
 */
export function globeSvg(box: { x: number; y: number; w: number; h: number }, id: string, data: {
  world: World; center: [number, number]; highlight?: { gid?: string; name?: string }; marker?: [number, number] | null;
  style: GlobeStyle; markerColor: string; lineWidth: number;
}) {
  const r = Math.min(box.w, box.h) / 2 - Math.max(0.4, data.lineWidth);
  const cx = box.x + box.w / 2, cy = box.y + box.h / 2;
  const proj = projector(data.center[0], Math.max(-60, Math.min(60, data.center[1])), cx, cy, r);
  const clip = `globe-${id}`;
  const st = data.style;
  const bw = Math.max(0.05, data.lineWidth * 0.35);
  let out = `<defs><clipPath id="${clip}"><circle cx="${n(cx)}" cy="${n(cy)}" r="${n(r)}"/></clipPath></defs>`;
  out += `<circle cx="${n(cx)}" cy="${n(cy)}" r="${n(r)}" fill="${st.ocean}"/>`;
  out += `<g clip-path="url(#${clip})">`;
  if (st.graticule) out += `<path d="${graticulePath(proj)}" fill="none" stroke="${st.border}" stroke-opacity="0.45" stroke-width="${n(bw * 0.8)}"/>`;
  const isHit = (f: WorldFeature) => (data.highlight?.gid && f.properties.gid === data.highlight.gid)
    || (!data.highlight?.gid && data.highlight?.name && f.properties.name.toLowerCase() === data.highlight.name.toLowerCase());
  let hit = "";
  for (const f of data.world.features) {
    const d = shapePath(f.geometry, proj);
    if (!d) continue;
    if (isHit(f)) { hit = d; continue; }
    out += `<path d="${d}" fill="${st.land}" stroke="${st.border}" stroke-width="${n(bw)}" stroke-linejoin="round"/>`;
  }
  if (hit) out += `<path d="${hit}" fill="${st.highlight}" stroke="${st.highlight}" stroke-width="${n(bw)}" stroke-linejoin="round"/>`;
  if (data.marker && st.marker !== false) {
    const [x, y, vis] = proj(data.marker[0], data.marker[1]);
    if (vis) {
      // Small enough not to hide the highlighted country.
      const m = Math.max(0.3, r * 0.02);
      out += `<circle cx="${n(x)}" cy="${n(y)}" r="${n(m)}" fill="${data.markerColor}" stroke="#ffffff" stroke-width="${n(m * 0.45)}"/>`;
    }
  }
  out += `</g><circle cx="${n(cx)}" cy="${n(cy)}" r="${n(r)}" fill="none" stroke="${st.border}" stroke-width="${n(Math.max(0.15, data.lineWidth * 0.6))}"/>`;
  return out;
}
