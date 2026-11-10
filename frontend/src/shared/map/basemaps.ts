// GEIDA basemaps: one list (backend apps/geoportal/catalog.py BASEMAPS) for every map,
// and one remembered choice shared with the Geo-Portal.
import { useQuery } from "@tanstack/react-query";

import { api } from "@/shared/api/client";

export type Basemap = {
  id: string;
  name: string;
  /** XYZ template; may use OpenLayers' {a-c} subdomain pattern. */
  url: string;
  thumb: string;
  attribution: string;
  maxZoom?: number;
};

/** Same localStorage key as the Geo-Portal engine ("geida." + "basemap"). */
const STORE_KEY = "geida.basemap";

export function useBasemaps() {
  return useQuery({
    queryKey: ["basemaps"],
    queryFn: () => api<{ basemaps: Basemap[] }>("/api/geoportal/basemaps/").then((d) => d.basemaps),
    staleTime: Infinity,
  });
}

export function savedBasemapId(): string | null {
  try {
    return localStorage.getItem(STORE_KEY);
  } catch {
    return null;
  }
}

export function saveBasemapId(id: string) {
  try {
    localStorage.setItem(STORE_KEY, id);
  } catch {
    /* private mode: the choice just isn't remembered */
  }
}

/** Tile URLs for MapLibre: expands "{a-c}" into one URL per subdomain. */
export function tileUrls(b: Basemap): string[] {
  const m = b.url.match(/\{([a-z])-([a-z])\}/);
  if (!m) return [b.url];
  const out: string[] = [];
  for (let c = m[1].charCodeAt(0); c <= m[2].charCodeAt(0); c++) out.push(b.url.replace(m[0], String.fromCharCode(c)));
  return out;
}
