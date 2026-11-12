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
  countries: { iso: string; name: string }[];
  live_count: number;
  total_count: number;
};
