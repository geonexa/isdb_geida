export type CatalogLayer = {
  id: string;
  name: string;
  source: string;
  res: string;
  period: string;
  kind: "cog" | "tiles" | "xyz" | "wms" | "arcgis_image" | "geojson" | "planned";
  desc: string;
  [key: string]: unknown;
};

export type CatalogGroup = { type: "raster" | "vector"; group: string; layers: CatalogLayer[] };

export type Basemap = { id: string; name: string; url: string; thumb: string; attribution: string; maxZoom?: number };

export type GeoportalConfig = {
  catalog: CatalogGroup[];
  basemaps: Basemap[];
  toolbox: { group: string; icon: string; tools: { id: string; hint: string; defaults?: Record<string, unknown> }[] }[];
  clippable: { id: string; name: string; source: string; years: number[]; year: number | null; scale: number | null }[];
  countries: { iso: string; name: string }[];
  live_count: number;
  total_count: number;
  tool_count: number;
};
