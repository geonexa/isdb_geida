/**
 * Raster basemaps for regions the default catalog does not serve well.
 *
 * Today that means mainland China: GeoLibre's defaults (OpenFreeMap, Protomaps)
 * and almost every provider in the Basemaps control are hosted outside it with
 * no presence inside, so from there they range from slow to unreachable. These
 * entries are served from inside China and give those users a basemap that
 * loads.
 *
 * The mechanism mirrors {@link PlanetaryBasemap}: `styleUrl` is a
 * `geolibre://regional-basemap/<id>` sentinel that the map controller's
 * `resolveMapStyle` expands into a raster style at apply time (it is not a
 * fetchable URL). A separate sentinel prefix from the planetary one keeps the
 * two apart, because selecting a planetary basemap also switches the project's
 * celestial body, which must not happen here.
 */

/**
 * The regions the pickers group these basemaps under. Each gets its own
 * heading and explanatory note inside the single "Regional" section, so a
 * future region slots in without the section itself becoming country-specific.
 */
export type RegionalBasemapRegionId = "china";

/**
 * A raster basemap for a region, rendered from XYZ (or TMS) tiles.
 */
export interface RegionalBasemap {
  id: string;
  /** Which region heading this basemap sits under. */
  region: RegionalBasemapRegionId;
  /**
   * Display name, in the language of the region the basemap serves. These are
   * Chinese-market services whose users know them by their Chinese names, and
   * the section heading already says which region they belong to, so the labels
   * are not translated the way UI strings are.
   */
  name: string;
  /** Sentinel stored as the basemap style URL. */
  styleUrl: string;
  /** XYZ (or TMS, see {@link scheme}) tile template. */
  tileUrl: string;
  /**
   * An optional transparent overlay drawn above {@link tileUrl}, so a satellite
   * basemap can ship with its roads and labels burnt in as one selectable
   * basemap rather than something the user has to stack by hand.
   */
  overlayTileUrl?: string;
  /**
   * Tile row ordering. Tencent numbers rows from the bottom (**TMS**); Amap is
   * standard XYZ. Omit for XYZ; MapLibre defaults to `"xyz"` when absent.
   */
  scheme?: "tms";
  /** Max native zoom of the source (MapLibre overzooms beyond this). */
  maxZoom: number;
  /** Attribution shown on the map. */
  attribution: string;
  /**
   * True when the tiles are drawn in GCJ-02, the offset datum Chinese law
   * mandates for public map services. Neither GeoLibre nor MapLibre applies the
   * shift, so WGS84 data laid over these lands roughly 100 to 700 m off (see
   * docs/getting-started.md). Not every regional basemap is offset — Tianditu
   * publishes in CGCS2000 and lines up — so this records which are, rather than
   * leaving a caveat that applies to some entries implied by the region.
   */
  gcj02?: boolean;
}

export const REGIONAL_BASEMAP_SENTINEL_PREFIX = "geolibre://regional-basemap/";

const AMAP_ATTRIBUTION = '&copy; <a href="https://www.amap.com">高德地图 Amap</a>';
const TENCENT_ATTRIBUTION = '&copy; <a href="https://map.qq.com">腾讯地图 Tencent Maps</a>';

const sentinel = (id: string) => `${REGIONAL_BASEMAP_SENTINEL_PREFIX}${id}`;

// Amap serves each product from four numbered hosts; MapLibre takes a single
// template per source, so pin host 01. Browsers multiplex over HTTP/2, which
// makes the sharding a non-issue. `style` selects the product: 7 street, 6
// imagery, 8 roads-and-labels.
const AMAP_STREET_URL =
  "https://wprd01.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scl=1&style=7&x={x}&y={y}&z={z}";
const AMAP_SATELLITE_URL = "https://webst01.is.autonavi.com/appmaptile?style=6&x={x}&y={y}&z={z}";
const AMAP_LABELS_URL = "https://webst01.is.autonavi.com/appmaptile?style=8&x={x}&y={y}&z={z}";

const tencentUrl = (styleId: number) =>
  `https://rt0.map.gtimg.com/tile?z={z}&x={x}&y={y}&styleid=${styleId}&scene=0`;

/**
 * Basemaps served from inside mainland China.
 *
 * Zoom limits are each source's probed maximum, so MapLibre overzooms (blurs)
 * rather than painting a placeholder: Amap's imagery returns a "no imagery"
 * tile rather than a 404 past zoom 18, and Tencent 400s past 19 with zoom 19
 * already blank.
 */
export const CHINA_BASEMAPS: readonly RegionalBasemap[] = [
  {
    id: "amap-street",
    region: "china",
    name: "高德地图",
    styleUrl: sentinel("amap-street"),
    tileUrl: AMAP_STREET_URL,
    maxZoom: 19,
    attribution: AMAP_ATTRIBUTION,
    gcj02: true,
  },
  {
    id: "amap-satellite",
    region: "china",
    name: "高德卫星",
    styleUrl: sentinel("amap-satellite"),
    tileUrl: AMAP_SATELLITE_URL,
    maxZoom: 18,
    attribution: AMAP_ATTRIBUTION,
    gcj02: true,
  },
  {
    id: "amap-hybrid",
    region: "china",
    name: "高德混合",
    styleUrl: sentinel("amap-hybrid"),
    tileUrl: AMAP_SATELLITE_URL,
    overlayTileUrl: AMAP_LABELS_URL,
    maxZoom: 18,
    attribution: AMAP_ATTRIBUTION,
    gcj02: true,
  },
  {
    id: "tencent-street",
    region: "china",
    name: "腾讯地图",
    styleUrl: sentinel("tencent-street"),
    tileUrl: tencentUrl(1),
    scheme: "tms",
    maxZoom: 18,
    attribution: TENCENT_ATTRIBUTION,
    gcj02: true,
  },
  {
    id: "tencent-dark",
    region: "china",
    name: "腾讯深色",
    styleUrl: sentinel("tencent-dark"),
    tileUrl: tencentUrl(4),
    scheme: "tms",
    maxZoom: 18,
    attribution: TENCENT_ATTRIBUTION,
    gcj02: true,
  },
];

/**
 * GEIDA platform basemaps — the same set the classic Geo-Portal offers, shown
 * in the map's basemap switcher. They resolve through the regional-basemap
 * sentinel mechanism (plain XYZ raster styles) but are not listed in the
 * "Regional" picker groups.
 */
export type RasterBasemapTiles = Omit<RegionalBasemap, "region">;

export interface GeidaBasemap extends RasterBasemapTiles {
  /** Small preview tile for the switcher. */
  thumb: string;
}

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";

export const GEIDA_BASEMAPS: readonly GeidaBasemap[] = [
  {
    id: "geida-light",
    name: "Light",
    styleUrl: sentinel("geida-light"),
    tileUrl: `${ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    thumb: `${ESRI}/Canvas/World_Light_Gray_Base/MapServer/tile/3/3/4`,
    maxZoom: 16,
    attribution: "&copy; Esri, HERE, Garmin, OpenStreetMap contributors",
  },
  {
    id: "geida-streets",
    name: "Streets",
    styleUrl: sentinel("geida-streets"),
    tileUrl: `${ESRI}/World_Street_Map/MapServer/tile/{z}/{y}/{x}`,
    thumb: `${ESRI}/World_Street_Map/MapServer/tile/3/3/4`,
    maxZoom: 19,
    attribution: "Tiles &copy; Esri, TomTom, Garmin, FAO, NOAA, USGS",
  },
  {
    id: "geida-satellite",
    name: "Satellite",
    styleUrl: sentinel("geida-satellite"),
    tileUrl: `${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`,
    thumb: `${ESRI}/World_Imagery/MapServer/tile/3/3/4`,
    maxZoom: 19,
    attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
  },
  {
    id: "geida-sentinel2",
    name: "Sentinel-2",
    styleUrl: sentinel("geida-sentinel2"),
    tileUrl:
      "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/{z}/{y}/{x}.jpg",
    thumb: "https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless-2020_3857/default/g/3/3/4.jpg",
    maxZoom: 15,
    attribution:
      "Sentinel-2 cloudless 2020 by EOX IT Services GmbH (contains modified Copernicus Sentinel data 2020)",
  },
  {
    id: "geida-terrain",
    name: "Terrain",
    styleUrl: sentinel("geida-terrain"),
    tileUrl: "https://a.tile.opentopomap.org/{z}/{x}/{y}.png",
    thumb: "https://a.tile.opentopomap.org/3/4/3.png",
    maxZoom: 17,
    attribution: "&copy; OpenStreetMap contributors, SRTM | &copy; OpenTopoMap (CC-BY-SA)",
  },
  {
    id: "geida-dark",
    name: "Dark",
    styleUrl: sentinel("geida-dark"),
    tileUrl: `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
    thumb: `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/3/3/4`,
    maxZoom: 16,
    attribution: "&copy; Esri, HERE, Garmin, OpenStreetMap contributors",
  },
];

/** The GEIDA basemap used when nothing else is chosen. */
export const GEIDA_DEFAULT_BASEMAP = GEIDA_BASEMAPS[0].styleUrl;

/** Look up a GEIDA basemap by its sentinel style URL. */
export function getGeidaBasemapByStyleUrl(styleUrl: string | undefined): GeidaBasemap | undefined {
  if (!styleUrl) return undefined;
  return GEIDA_BASEMAPS.find((basemap) => basemap.styleUrl === styleUrl);
}

/** Every regional basemap, across all regions. */
export const REGIONAL_BASEMAPS: readonly RegionalBasemap[] = CHINA_BASEMAPS;

/**
 * The regional basemaps grouped for display, one entry per region. Both the New
 * Project and Change Basemap panels render this inside a single collapsible
 * "Regional" section, so adding a region is a change here rather than in two
 * dialogs.
 */
export const REGIONAL_BASEMAP_GROUPS: readonly {
  id: RegionalBasemapRegionId;
  basemaps: readonly RegionalBasemap[];
}[] = [{ id: "china", basemaps: CHINA_BASEMAPS }];

/** Look up a regional basemap by its `geolibre://regional-basemap/<id>` sentinel. */
export function getRegionalBasemapByStyleUrl(
  styleUrl: string | undefined,
): RasterBasemapTiles | undefined {
  if (!styleUrl) return undefined;
  return (
    REGIONAL_BASEMAPS.find((basemap) => basemap.styleUrl === styleUrl) ??
    getGeidaBasemapByStyleUrl(styleUrl)
  );
}

/** Look up a regional basemap by id. */
export function getRegionalBasemapById(id: string | undefined): RegionalBasemap | undefined {
  if (!id) return undefined;
  return REGIONAL_BASEMAPS.find((basemap) => basemap.id === id);
}

/** Whether a style URL is a regional-basemap sentinel, resolvable or not. */
export function isRegionalBasemapSentinel(styleUrl: string | undefined): boolean {
  return Boolean(styleUrl?.startsWith(REGIONAL_BASEMAP_SENTINEL_PREFIX));
}
