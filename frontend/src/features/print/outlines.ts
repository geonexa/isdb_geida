/**
 * Boundaries for overview maps: the project's country and the region (admin level 1)
 * holding the area, from the GADM boundaries API. If boundaries aren't loaded on this
 * server, the country falls back to the member-country outlines shipped with the app.
 */
import type { Geometry, MultiPolygon, Polygon } from "geojson";

import type { BBox } from "@/features/print/capture";
import { api } from "@/shared/api/client";

export type Outline = { name: string; bbox: BBox; geometry: Polygon | MultiPolygon; gid?: string };
export type Outlines = { country?: Outline; region?: Outline };

type Unit = { gid: string; name: string; level: number };
type Feature = { properties: { name?: string }; geometry: Geometry | null };

const isArea = (g: Geometry | null): g is Polygon | MultiPolygon => !!g && (g.type === "Polygon" || g.type === "MultiPolygon");

export function bboxOf(g: Polygon | MultiPolygon): BBox {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
  for (const poly of polys) for (const ring of poly) for (const [x, y] of ring) {
    if (x < w) w = x; if (x > e) e = x; if (y < s) s = y; if (y > n) n = y;
  }
  return [w, s, e, n];
}

async function unitOutline(gid: string): Promise<Outline | undefined> {
  const f = await api<Feature>(`/api/boundaries/units/${encodeURIComponent(gid)}/`);
  return isArea(f.geometry) ? { name: f.properties.name ?? gid, bbox: bboxOf(f.geometry), geometry: f.geometry, gid } : undefined;
}

async function memberCountry(name: string): Promise<Outline | undefined> {
  const fc = await fetch("/data/isdb_member_countries.geojson").then((r) => r.json()) as { features: Feature[] };
  const f = fc.features.find((x) => x.properties.name?.toLowerCase() === name.toLowerCase());
  return f && isArea(f.geometry) ? { name, bbox: bboxOf(f.geometry), geometry: f.geometry } : undefined;
}

export async function loadOutlines(areaBbox: BBox | null | undefined, countryName: string): Promise<Outlines> {
  const out: Outlines = {};
  if (areaBbox) {
    try {
      const lon = (areaBbox[0] + areaBbox[2]) / 2, lat = (areaBbox[1] + areaBbox[3]) / 2;
      const { units } = await api<{ units: Unit[] }>(`/api/boundaries/at/?lon=${lon}&lat=${lat}&level=1`);
      const country = units.find((u) => u.level === 0), region = units.find((u) => u.level === 1);
      const [c, r] = await Promise.all([country && unitOutline(country.gid), region && unitOutline(region.gid)]);
      if (c) out.country = c;
      if (r) out.region = r;
    } catch { /* boundaries not loaded on this server */ }
  }
  if (!out.country && countryName) {
    try { out.country = await memberCountry(countryName); } catch { /* no outline: the overview still frames the country box */ }
  }
  return out;
}
