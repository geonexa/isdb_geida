/**
 * Map layout model (QGIS-style print layout): a page and a list of items placed on
 * it in millimetres. Items are drawn in list order (last on top). Saved per project
 * in the browser; layouts can also be saved as named templates and reused.
 */

/* --------------------------------------------------------------- context */

export type LegendSwatch = { color: string; label?: string; size?: number };
export type LegendEntry = { id: string; name: string; swatches: LegendSwatch[] };

/** A continuous layer on the map, drawn as a colour bar. */
export type Ramp = { colors: string[]; min: number; max: number; label: string };

/** What the project page knows about the map being exported. */
export type PrintContext = {
  title: string;
  subtitle: string;
  code: string;
  author: string;
  sources: string[];
  country?: string;
};

export const DISCLAIMER = "The boundaries, names and designations used on this map do not imply official endorsement or acceptance by the Islamic Development Bank.";
export const ISDB_LOGO = "/img/isdb-logo.png";

/* --------------------------------------------------------------- page */

export type PaperId = "a5" | "a4" | "a3" | "a2" | "a1" | "a0" | "letter" | "legal" | "tabloid" | "custom";
export const PAPERS: { id: PaperId; label: string; w: number; h: number }[] = [
  { id: "a5", label: "A5", w: 148, h: 210 },
  { id: "a4", label: "A4", w: 210, h: 297 },
  { id: "a3", label: "A3", w: 297, h: 420 },
  { id: "a2", label: "A2", w: 420, h: 594 },
  { id: "a1", label: "A1", w: 594, h: 841 },
  { id: "a0", label: "A0", w: 841, h: 1189 },
  { id: "letter", label: "Letter", w: 215.9, h: 279.4 },
  { id: "legal", label: "Legal", w: 215.9, h: 355.6 },
  { id: "tabloid", label: "Tabloid", w: 279.4, h: 431.8 },
  { id: "custom", label: "Custom", w: 300, h: 200 },
];

export type Page = {
  paper: PaperId;
  orientation: "landscape" | "portrait";
  custom: { w: number; h: number };
  background: string;
  /** Margin guides, mm (also where templates place things). */
  margin: number;
  border: { show: boolean; color: string; width: number };
};

export function pageSize(p: Page) {
  if (p.paper === "custom") return { w: p.custom.w, h: p.custom.h };
  const s = PAPERS.find((x) => x.id === p.paper)!;
  const [a, b] = [Math.min(s.w, s.h), Math.max(s.w, s.h)];
  return p.orientation === "landscape" ? { w: b, h: a } : { w: a, h: b };
}

/* --------------------------------------------------------------- items */

export type Frame = {
  /** Background fill ("" = none) and its opacity. */
  bg: string;
  bgOpacity: number;
  /** Outline ("" = none) and width in mm. */
  stroke: string;
  strokeWidth: number;
  /** Inner padding, mm. */
  padding: number;
  /** Drop shadow (subtle). */
  shadow: boolean;
};
export const NO_FRAME: Frame = { bg: "", bgOpacity: 1, stroke: "", strokeWidth: 0.25, padding: 0, shadow: false };
export const PLATE: Frame = { bg: "#ffffff", bgOpacity: 0.9, stroke: "#9ca3af", strokeWidth: 0.2, padding: 2, shadow: false };

export type FontFamily = "sans" | "serif" | "mono";
export type Font = { family: FontFamily; size: number /* pt */; weight: 400 | 500 | 600 | 700; italic: boolean; color: string };

type Base = {
  id: string;
  name: string;
  x: number; y: number; w: number; h: number;
  visible: boolean;
  locked: boolean;
  frame: Frame;
};

export type Grid = {
  show: boolean;
  /** Degrees between lines; 0 = automatic. */
  interval: number;
  style: "lines" | "crosses";
  color: string;
  width: number;
  labels: "none" | "inside" | "outside";
  format: "dms" | "decimal";
  labelSize: number;
  /** Alternating black/white border (outside labels only). */
  zebra: boolean;
};

export type MapItem = Base & {
  type: "map";
  /** view = the project map's view; area = the project's area; custom = centre + scale (pan/zoom it here). */
  extent: "view" | "area" | "custom";
  center: [number, number];
  scale: number;
  grid: Grid;
};
export type OverviewItem = Base & {
  type: "overview";
  /** The map whose extent is outlined. */
  mapId: string;
  /** country = the project's country; region = its province/region (admin level 1); around = the main map's extent zoomed out;
   * globe = a vector globe locator centred on the country (no map capture). */
  extent: "country" | "region" | "around" | "globe";
  zoomOut: number;
  boxColor: string;
  boxWidth: number;
  /** Draw the country (and, for "region", the region) boundary. Older saved layouts lack these: treat as on. */
  outline?: boolean;
  outlineColor?: string;
  outlineWidth?: number;
  /** Colours of the globe locator (extent "globe"). */
  globe?: { ocean: string; land: string; border: string; highlight: string; graticule: boolean; marker?: boolean };
};
export type TextItem = Base & {
  type: "text";
  text: string;
  font: Font;
  align: "left" | "center" | "right";
  valign: "top" | "middle" | "bottom";
  lineHeight: number;
  /** White outline around letters, for text over the map. */
  halo: boolean;
};
export type LegendItem = Base & {
  type: "legend";
  title: string;
  titleFont: Font;
  labelFont: Font;
  columns: number;
  symbolW: number;
  symbolH: number;
  /** Fit the box to its contents. */
  auto: boolean;
  /** Per entry: a new name, or hidden. */
  edits: Record<string, { name?: string; hidden?: boolean }>;
};
export type ScaleBarItem = Base & {
  type: "scalebar";
  mapId: string;
  style: "single" | "double" | "line" | "hollow";
  units: "km" | "m" | "mi";
  segments: number;
  /** Bar height, mm. */
  barHeight: number;
  font: Font;
  color: string;
  /** "1:50,000" under the bar. */
  showRatio: boolean;
};
export type NorthItem = Base & { type: "north"; style: "arrow" | "star" | "simple"; color: string };
export type ColorbarItem = Base & {
  type: "colorbar";
  orientation: "horizontal" | "vertical";
  label: string;
  ticks: number;
  font: Font;
};
export type PictureItem = Base & { type: "picture"; src: string; fit: "contain" | "cover" };
export type ShapeItem = Base & { type: "shape"; shape: "rect" | "ellipse" | "line"; fill: string; fillOpacity: number; stroke: string; strokeWidth: number };

export type Item = MapItem | OverviewItem | TextItem | LegendItem | ScaleBarItem | NorthItem | ColorbarItem | PictureItem | ShapeItem;
export type ItemType = Item["type"];

export type Layout = { version: 2; template: string; page: Page; items: Item[] };

export const ITEM_LABEL: Record<ItemType, string> = {
  map: "Map", overview: "Overview map", text: "Text", legend: "Legend", scalebar: "Scale bar",
  north: "North arrow", colorbar: "Colour bar", picture: "Picture", shape: "Shape",
};

/* --------------------------------------------------------------- defaults */

let seq = 0;
export const uid = (type: string) => `${type}-${Date.now().toString(36)}-${(seq++).toString(36)}`;

export const font = (size: number, weight: Font["weight"] = 400, p: Partial<Font> = {}): Font =>
  ({ family: "sans", size, weight, italic: false, color: "#1f2937", ...p });

export const DEFAULT_GRID: Grid = {
  show: true, interval: 0, style: "lines", color: "#475569", width: 0.12,
  labels: "outside", format: "dms", labelSize: 6, zebra: true,
};

/** A new item of `type`, placed at x/y. */
export function newItem(type: ItemType, x: number, y: number, ctx: { mapId?: string; ramp?: Ramp | null } = {}): Item {
  const base = { id: uid(type), x, y, visible: true, locked: false, frame: { ...NO_FRAME } };
  switch (type) {
    case "map":
      return { ...base, type, name: "Map", w: 120, h: 80, extent: "view", center: [0, 0], scale: 50000, grid: { ...DEFAULT_GRID, show: false }, frame: { ...NO_FRAME, stroke: "#1f2937", strokeWidth: 0.3 } };
    case "overview":
      return { ...base, type, name: "Overview map", w: 50, h: 40, mapId: ctx.mapId ?? "", extent: "globe", zoomOut: 6, boxColor: "#d7263d", boxWidth: 0.6, outline: true, outlineColor: "#0B3B47", outlineWidth: 0.35, frame: { ...NO_FRAME, stroke: "#1f2937", strokeWidth: 0.25 } };
    case "text":
      return { ...base, type, name: "Text", w: 60, h: 10, text: "Text", font: font(10), align: "left", valign: "top", lineHeight: 1.25, halo: false };
    case "legend":
      return { ...base, type, name: "Legend", w: 50, h: 30, title: "Legend", titleFont: font(9, 700), labelFont: font(7.5), columns: 1, symbolW: 5, symbolH: 3.5, auto: true, edits: {}, frame: { ...PLATE } };
    case "scalebar":
      return { ...base, type, name: "Scale bar", w: 60, h: 10, mapId: ctx.mapId ?? "", style: "single", units: "km", segments: 4, barHeight: 1.6, font: font(6.5), color: "#1f2937", showRatio: false };
    case "north":
      return { ...base, type, name: "North arrow", w: 10, h: 14, style: "arrow", color: "#1f2937" };
    case "colorbar":
      return { ...base, type, name: "Colour bar", w: 50, h: 12, orientation: "horizontal", label: ctx.ramp?.label ?? "Value", ticks: 3, font: font(6.5) };
    case "picture":
      return { ...base, type, name: "Picture", w: 30, h: 15, src: ISDB_LOGO, fit: "contain" };
    case "shape":
      return { ...base, type, name: "Rectangle", w: 40, h: 20, shape: "rect", fill: "#ffffff", fillOpacity: 0, stroke: "#1f2937", strokeWidth: 0.3 };
  }
}

/* --------------------------------------------------------------- templates */

export type TemplateId = "classic" | "report" | "poster" | "clean";
export const TEMPLATES: { id: TemplateId; label: string; desc: string; page: Partial<Page> }[] = [
  { id: "classic", label: "Classic", desc: "Title band, map, side panel with overview, legend and notes", page: { paper: "a4", orientation: "landscape" } },
  { id: "report", label: "Report figure", desc: "Portrait: map on top, legend and overview below", page: { paper: "a4", orientation: "portrait" } },
  { id: "poster", label: "Poster", desc: "A3 landscape, large title, wide side panel", page: { paper: "a3", orientation: "landscape" } },
  { id: "clean", label: "Map only", desc: "Full-page map, everything on plates over it", page: { paper: "a4", orientation: "landscape" } },
];

export const DEFAULT_PAGE: Page = {
  paper: "a4", orientation: "landscape", custom: { w: 300, h: 200 }, background: "#ffffff", margin: 8,
  border: { show: false, color: "#1f2937", width: 0.5 },
};

const SOURCES_TEXT = "{sources}";
const FOOTER_TEXT = "Map: GEIDA, IsDB Geoinformatics Data Platform · {date} · Project {code}";

/** Build a template's items for a page. Text uses {variables}, so templates work for any project. */
export function buildTemplate(id: TemplateId, page: Page, ramp: Ramp | null): Layout {
  const { w: W, h: H } = pageSize(page);
  const m = page.margin;
  const s = Math.min(W, H) / 210; // type scale: 1 on A4
  const items: Item[] = [];
  const add = <T extends Item>(it: T) => { items.push(it); return it; };
  const text = (name: string, x: number, y: number, w: number, h: number, t: string, f: Font, p: Partial<TextItem> = {}) =>
    add({ ...(newItem("text", x, y) as TextItem), name, w, h, text: t, font: f, ...p });

  if (id === "clean") {
    const map = add({ ...(newItem("map", m, m) as MapItem), w: W - 2 * m, h: H - 2 * m, grid: { ...DEFAULT_GRID, labels: "inside", zebra: false } });
    const tw = Math.min(150 * s, W * 0.55);
    add({ ...(newItem("shape", m + 5, m + 5) as ShapeItem), name: "Title plate", w: tw, h: 20 * s, fill: "#ffffff", fillOpacity: 0.9, stroke: "#9ca3af", strokeWidth: 0.2 });
    text("Title", m + 5 + 3 * s, m + 5 + 3 * s, tw - 6 * s, 8 * s, "{title}", font(15 * s, 700, { color: "#0b3b47" }));
    text("Subtitle", m + 5 + 3 * s, m + 5 + 12 * s, tw - 6 * s, 6 * s, "{subtitle}", font(9 * s, 400, { color: "#4b5563" }));
    add({ ...(newItem("picture", W - m - 5 - 36 * s, m + 5) as PictureItem), name: "IsDB logo", w: 36 * s, h: 14 * s, frame: { ...PLATE, stroke: "" } });
    add({ ...(newItem("north", W - m - 5 - 9 * s, m + 24 * s) as NorthItem), w: 9 * s, h: 13 * s, frame: { ...PLATE, padding: 1 } });
    add({ ...(newItem("legend", W - m - 5 - 52 * s, H - m - 60 * s) as LegendItem), w: 52 * s, h: 40 * s });
    if (ramp) add({ ...(newItem("colorbar", m + 5, H - m - 46 * s, { ramp }) as ColorbarItem), w: 56 * s, h: 14 * s, frame: { ...PLATE } });
    add({ ...(newItem("scalebar", m + 5, H - m - 26 * s, { mapId: map.id }) as ScaleBarItem), w: 60 * s, h: 11 * s, frame: { ...PLATE }, showRatio: true });
    scaleFurniture(items, s);
    text("Sources", m + 5, H - m - 13 * s, W * 0.6, 8 * s, `${SOURCES_TEXT}  ${FOOTER_TEXT}`, font(5.5 * s, 400, { color: "#374151" }), { frame: { ...PLATE, padding: 1.2 } });
    return { version: 2, template: id, page, items };
  }

  const portrait = id === "report";
  const titleSize = (id === "poster" ? 24 : 17) * s;
  const logoW = 34 * s, logoH = 13 * s;
  // Title band
  text("Title", m, m, W - 2 * m - logoW - 6, titleSize * 0.55, "{title}", font(titleSize, 700, { color: "#0b3b47" }));
  text("Subtitle", m, m + titleSize * 0.55, W - 2 * m - logoW - 6, 7 * s, "{subtitle}", font(10 * s, 400, { color: "#4b5563" }));
  add({ ...(newItem("picture", W - m - logoW, m) as PictureItem), name: "IsDB logo", w: logoW, h: logoH });
  const bandBottom = m + Math.max(logoH, titleSize * 0.55 + 7 * s) + 3;
  add({ ...(newItem("shape", m, bandBottom) as ShapeItem), name: "Title rule", shape: "line", w: W - 2 * m, h: 0, stroke: "#0b3b47", strokeWidth: 0.6 });
  const top = bandBottom + 3;
  const footerH = 6 * s;
  const bottom = H - m - footerH - 2;
  const gridOut = 5; // room for outside grid labels

  if (portrait) {
    const mapH = (bottom - top) * 0.62;
    const map = add({ ...(newItem("map", m + gridOut, top + gridOut) as MapItem), w: W - 2 * m - 2 * gridOut, h: mapH - 2 * gridOut, grid: { ...DEFAULT_GRID } });
    add({ ...(newItem("north", map.x + map.w - 13 * s, map.y + 3) as NorthItem), w: 9 * s, h: 13 * s, frame: { ...PLATE, padding: 1 } });
    add({ ...(newItem("scalebar", map.x + 3, map.y + map.h - 14 * s, { mapId: map.id }) as ScaleBarItem), w: 58 * s, h: 11 * s, frame: { ...PLATE }, showRatio: true });
    const lowTop = top + mapH + 3;
    const colW = (W - 2 * m - 6) / 2;
    add({ ...(newItem("legend", m, lowTop) as LegendItem), w: colW, h: 40 * s, frame: { ...NO_FRAME, stroke: "#d1d5db", strokeWidth: 0.2, padding: 3 } });
    add({ ...(newItem("overview", m + colW + 6, lowTop, { mapId: map.id }) as OverviewItem), w: colW, h: Math.min(colW * 0.7, bottom - lowTop - 34 * s) });
    if (ramp) add({ ...(newItem("colorbar", m, lowTop + 46 * s, { ramp }) as ColorbarItem), w: colW, h: 14 * s });
    text("Notes", m, bottom - 26 * s, W - 2 * m, 26 * s, `${SOURCES_TEXT}\n\n${DISCLAIMER}`, font(6.5 * s, 400, { color: "#4b5563" }), { lineHeight: 1.35 });
  } else {
    const sideW = (id === "poster" ? 82 : 64) * s;
    const map = add({ ...(newItem("map", m + gridOut, top + gridOut) as MapItem), w: W - 2 * m - sideW - 6 - 2 * gridOut, h: bottom - top - 2 * gridOut, grid: { ...DEFAULT_GRID } });
    add({ ...(newItem("north", map.x + map.w - 13 * s, map.y + 3) as NorthItem), w: 9 * s, h: 13 * s, frame: { ...PLATE, padding: 1 } });
    add({ ...(newItem("scalebar", map.x + 3, map.y + map.h - 14 * s, { mapId: map.id }) as ScaleBarItem), w: 62 * s, h: 11 * s, frame: { ...PLATE }, showRatio: true });
    const sx = W - m - sideW;
    const ovH = sideW * 0.72;
    add({ ...(newItem("overview", sx, top + gridOut, { mapId: map.id }) as OverviewItem), w: sideW, h: ovH });
    text("Overview caption", sx, top + gridOut + ovH + 1, sideW, 5 * s, "Location: {country}", font(6.5 * s, 400, { italic: true, color: "#4b5563" }));
    let y = top + gridOut + ovH + 9 * s;
    add({ ...(newItem("legend", sx, y) as LegendItem), w: sideW, h: 45 * s, frame: { ...NO_FRAME, padding: 0 } });
    y += 52 * s;
    if (ramp) { add({ ...(newItem("colorbar", sx, y, { ramp }) as ColorbarItem), w: sideW, h: 14 * s }); y += 18 * s; }
    text("Notes", sx, Math.max(y, bottom - 52 * s), sideW, bottom - Math.max(y, bottom - 52 * s), `${SOURCES_TEXT}\n\n${DISCLAIMER}`, font(6 * s, 400, { color: "#4b5563" }), { lineHeight: 1.35, valign: "bottom" });
  }
  scaleFurniture(items, s);
  add({ ...(newItem("shape", m, H - m - footerH) as ShapeItem), name: "Footer rule", shape: "line", w: W - 2 * m, h: 0, stroke: "#d1d5db", strokeWidth: 0.25 });
  text("Footer", m, H - m - footerH + 1.5, W - 2 * m, footerH - 1.5, FOOTER_TEXT, font(6 * s, 400, { color: "#6b7280" }));
  return { version: 2, template: id, page, items };
}

/** Legend, scale bar, colour bar and grid type sized for the page (they're created at A4 sizes). */
function scaleFurniture(items: Item[], s: number) {
  if (Math.abs(s - 1) < 0.05) return;
  const f = (x: Font) => ({ ...x, size: Math.round(x.size * s * 2) / 2 });
  for (const it of items) {
    if (it.type === "legend") Object.assign(it, { titleFont: f(it.titleFont), labelFont: f(it.labelFont), symbolW: it.symbolW * s, symbolH: it.symbolH * s });
    if (it.type === "scalebar" || it.type === "colorbar") Object.assign(it, { font: f(it.font) });
    if (it.type === "scalebar") it.barHeight *= s;
    if (it.type === "map") it.grid = { ...it.grid, labelSize: Math.round(it.grid.labelSize * s * 2) / 2 };
  }
}

export function defaultLayout(ramp: Ramp | null): Layout {
  return buildTemplate("classic", { ...DEFAULT_PAGE }, ramp);
}

/** New page size: move and stretch items in proportion (text sizes stay). */
export function fitToPage(layout: Layout, page: Page): Layout {
  const a = pageSize(layout.page), b = pageSize(page);
  const fx = b.w / a.w, fy = b.h / a.h;
  return {
    ...layout, page,
    items: layout.items.map((it) => ({ ...it, x: it.x * fx, y: it.y * fy, w: it.w * fx, h: it.h * fy })),
  };
}

/* --------------------------------------------------------------- variables */

export type Vars = Record<string, string>;
export function fillVars(text: string, vars: Vars) {
  return text.replace(/\{(\w+)\}/g, (all, k: string) => (k in vars ? vars[k] : all));
}
export const VARIABLES = ["title", "subtitle", "code", "country", "author", "date", "scale", "sources", "crs"];

/* --------------------------------------------------------------- storage */

const KEY = (code: string) => `geida.layout.v2.${code}`;
const TPL_KEY = "geida.layout.templates";

export function loadLayout(code: string, ramp: Ramp | null): Layout {
  try {
    const raw = localStorage.getItem(KEY(code));
    if (raw) {
      const l = JSON.parse(raw) as Layout;
      if (l.version === 2 && Array.isArray(l.items)) return l;
    }
  } catch { /* fall through */ }
  return defaultLayout(ramp);
}
export function saveLayout(code: string, l: Layout) {
  try { localStorage.setItem(KEY(code), JSON.stringify(l)); } catch { /* storage full or blocked: saving is a convenience */ }
}

export type SavedTemplate = { name: string; saved: string; layout: Layout };
export function listTemplates(): SavedTemplate[] {
  try { return JSON.parse(localStorage.getItem(TPL_KEY) ?? "[]"); } catch { return []; }
}
export function storeTemplate(name: string, layout: Layout) {
  const all = listTemplates().filter((t) => t.name !== name);
  all.unshift({ name, saved: new Date().toISOString(), layout });
  try { localStorage.setItem(TPL_KEY, JSON.stringify(all.slice(0, 20))); } catch { throw new Error("The browser's storage is full; remove a template or a large picture."); }
}
export function deleteTemplate(name: string) {
  try { localStorage.setItem(TPL_KEY, JSON.stringify(listTemplates().filter((t) => t.name !== name))); } catch { /* ignore */ }
}
/** A saved template with fresh item ids (so two copies never share ids). */
export function instantiate(t: Layout): Layout {
  const ids = new Map(t.items.map((it) => [it.id, uid(it.type)]));
  return {
    ...t,
    items: t.items.map((it) => {
      const n = { ...it, id: ids.get(it.id)! } as Item;
      if ((n.type === "scalebar" || n.type === "overview") && ids.has(n.mapId)) n.mapId = ids.get(n.mapId)!;
      return n;
    }),
  };
}
