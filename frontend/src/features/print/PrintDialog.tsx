import "@/features/print/print.css";

import type * as maplibregl from "maplibre-gl";
import {
  ArrowDown, ArrowUp, Compass, Copy, Earth, Eye, EyeOff, FileCode, FileImage, FileText, Grid3x3, Image as ImageIcon,
  LayoutTemplate, List, LoaderCircle, Lock, LockOpen, Magnet, Map as MapIcon, Maximize, Move, Printer, Rainbow, Redo2,
  Ruler, Save, Square, Trash2, Type, Undo2, Upload, X, ZoomIn, ZoomOut,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { useConfirm } from "@/shared/components/Confirm";

import { captureMap, MM_TO_CSS, projector, scaleOf, type BBox, type Camera } from "@/features/print/capture";
import { copyPng, embeddedFontCss, exportPdf, exportPng, exportSvg, loadPicture, printPage, toDataUrl, usableDpi } from "@/features/print/export";
import {
  buildTemplate, deleteTemplate, fitToPage, instantiate, ISDB_LOGO, ITEM_LABEL, listTemplates, loadLayout,
  newItem, pageSize, PAPERS, saveLayout, storeTemplate, TEMPLATES, uid, VARIABLES,
  type ColorbarItem, type Font, type Frame, type Item, type ItemType, type Layout, type LegendEntry, type LegendItem,
  type MapItem, type NorthItem, type OverviewItem, type Page, type PictureItem, type PrintContext, type Ramp,
  type SavedTemplate, type ScaleBarItem, type ShapeItem, type TemplateId, type TextItem, type Vars,
} from "@/features/print/layout";
import { DEFAULT_GLOBE, loadWorld, type World } from "@/features/print/globe";
import { loadOutlines, type Outlines } from "@/features/print/outlines";
import { renderLayout, roundScale, type Box, type Env, type MapImage } from "@/features/print/render";

export type PrintDialogProps = {
  map: maplibregl.Map;
  code: string;
  context: PrintContext;
  legend: LegendEntry[];
  areaBbox?: BBox | null;
  /** The project country's box, for overview maps. */
  countryBbox?: BBox | null;
  /** A continuous layer on the map (e.g. NDVI), offered as a colour bar. */
  ramp?: Ramp | null;
  onClose: () => void;
};

const DPIS = [150, 300, 600];
const MAX_PICTURE_BYTES = 1.5 * 1024 * 1024;
const PREVIEW_DPI = 144;
const ADDABLE: { type: ItemType; icon: typeof MapIcon }[] = [
  { type: "map", icon: MapIcon }, { type: "overview", icon: Earth }, { type: "text", icon: Type }, { type: "legend", icon: List },
  { type: "scalebar", icon: Ruler }, { type: "north", icon: Compass }, { type: "colorbar", icon: Rainbow },
  { type: "picture", icon: ImageIcon }, { type: "shape", icon: Square },
];
const ICON: Record<ItemType, typeof MapIcon> = Object.fromEntries(ADDABLE.map((a) => [a.type, a.icon])) as Record<ItemType, typeof MapIcon>;

/* ------------------------------------------------------------------ history */

function useHistory(initial: () => Layout) {
  const [present, setPresent] = useState(initial);
  const past = useRef<Layout[]>([]);
  const future = useRef<Layout[]>([]);
  const last = useRef<{ key: string; t: number }>({ key: "", t: 0 });
  const [, force] = useState(0);
  /** A change worth undoing. Repeated changes with the same key (typing) merge into one step. */
  const commit = useCallback((fn: (l: Layout) => Layout, key = "") => {
    setPresent((cur) => {
      const now = Date.now();
      if (!(key && last.current.key === key && now - last.current.t < 900)) {
        past.current = [...past.current.slice(-79), cur];
        future.current = [];
      }
      last.current = { key, t: now };
      return fn(cur);
    });
    force((x) => x + 1);
  }, []);
  /** Changes during a drag: one undo step for the whole gesture (call begin() first). */
  const begin = useCallback(() => setPresent((cur) => { past.current = [...past.current.slice(-79), cur]; future.current = []; last.current = { key: "", t: 0 }; return cur; }), []);
  const transient = useCallback((fn: (l: Layout) => Layout) => setPresent(fn), []);
  const undo = useCallback(() => setPresent((cur) => { const p = past.current.pop(); if (!p) return cur; future.current.push(cur); force((x) => x + 1); return p; }), []);
  const redo = useCallback(() => setPresent((cur) => { const f = future.current.pop(); if (!f) return cur; past.current.push(cur); force((x) => x + 1); return f; }), []);
  return { layout: present, commit, begin, transient, undo, redo, canUndo: past.current.length > 0, canRedo: future.current.length > 0 };
}

/* ------------------------------------------------------------------ dialog */

type Drag = {
  id: string; handle: string; start: [number, number]; box: Box;
  /** Map content pan (instead of moving the item). */
  pan?: boolean;
};

/**
 * Map layout editor, after QGIS's print layout: a page with items you place, move
 * and resize (maps with grids, overview map, legend, scale bar, north arrow, colour
 * bar, text, pictures, shapes); a list of the items; and the selected item's
 * properties. Exports to vector SVG, PNG, PDF or the printer.
 */
export default function PrintDialog({ map, code, context, legend, areaBbox, countryBbox, ramp = null, onClose }: PrintDialogProps) {
  const h = useHistory(() => loadLayout(code, ramp));
  const confirm = useConfirm();
  const { layout, commit, begin, transient } = h;
  const [sel, setSel] = useState<string | null>(null);
  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [snap, setSnap] = useState(true);
  const [guides, setGuides] = useState(true);
  const [panMode, setPanMode] = useState<string | null>(null);
  const [dpi, setDpi] = useState(() => Number(localStorage.getItem("geida.layout.dpi")) || 300);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [caps, setCaps] = useState<Record<string, MapImage & { key: string }>>({});
  const [capturing, setCapturing] = useState(0);
  const [pictures, setPictures] = useState<Env["pictures"]>({});
  const [offsets, setOffsets] = useState<Record<string, [number, number]>>({});
  const [snapLines, setSnapLines] = useState<{ x: number[]; y: number[] }>({ x: [], y: [] });
  const [templates, setTemplates] = useState<SavedTemplate[]>(listTemplates);
  // Country and region boundaries for overview maps (null while loading).
  const [outlines, setOutlines] = useState<Outlines | null>(null);
  useEffect(() => { loadOutlines(areaBbox, context.country ?? "").then(setOutlines); }, []);
  // World outlines for globe locators, loaded the first time a globe is shown (null = failed).
  const [world, setWorld] = useState<World | null | undefined>(undefined);
  const wantsGlobe = layout.items.some((i) => i.type === "overview" && (i as OverviewItem).extent === "globe");
  useEffect(() => { if (wantsGlobe && world === undefined) loadWorld().then(setWorld).catch(() => setWorld(null)); }, [wantsGlobe]);
  const drag = useRef<Drag | null>(null);
  const svg = useRef<SVGSVGElement>(null);
  const canvasEl = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ w: 800, h: 600 });

  useEffect(() => { saveLayout(code, layout); }, [code, layout]);
  useEffect(() => { try { localStorage.setItem("geida.layout.dpi", String(dpi)); } catch { /* ignore */ } }, [dpi]);

  const { w: W, h: H } = pageSize(layout.page);
  const item = layout.items.find((i) => i.id === sel) ?? null;
  const maps = layout.items.filter((i): i is MapItem => i.type === "map");

  /* ---------------- canvas size and zoom */
  useEffect(() => {
    const el = canvasEl.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setCanvasSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const fitScale = Math.max(0.5, Math.min((canvasSize.w - 64) / W, (canvasSize.h - 64) / H));
  const pxPerMm = zoom === "fit" ? fitScale : zoom;

  /* ---------------- map captures (preview) */
  const cameraFor = useCallback((it: MapItem): Camera => {
    if (it.extent === "area" && areaBbox) return { kind: "bounds", bbox: areaBbox, padding: Math.min(it.w, it.h) * MM_TO_CSS * 0.06 };
    if (it.extent === "custom") return { kind: "center", center: it.center, scale: it.scale };
    const b = map.getBounds();
    return { kind: "bounds", bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()] };
  }, [map, areaBbox]);

  const overviewCamera = useCallback((it: OverviewItem, main?: MapImage): Camera | null => {
    if (it.extent === "globe") return null; // drawn as vectors, no capture
    const pad = Math.min(it.w, it.h) * MM_TO_CSS * 0.08;
    if (it.extent === "region" && outlines?.region) return { kind: "bounds", bbox: outlines.region.bbox, padding: pad };
    if (it.extent !== "around") {
      const box = outlines?.country?.bbox ?? countryBbox;
      if (box) return { kind: "bounds", bbox: box, padding: pad };
    }
    if (!main) return null;
    const [w, s, e, n] = main.cap.bounds;
    const cx = (w + e) / 2, cy = (s + n) / 2, k = Math.max(1.5, it.zoomOut);
    const hw = Math.min(179, ((e - w) / 2) * k), hh = Math.min(80, ((n - s) / 2) * k);
    return { kind: "bounds", bbox: [Math.max(-180, cx - hw), Math.max(-85, cy - hh), Math.min(180, cx + hw), Math.min(85, cy + hh)] };
  }, [countryBbox, outlines]);

  const mapKey = (it: MapItem) => `${it.w.toFixed(1)}x${it.h.toFixed(1)}|${it.extent}|${it.extent === "custom" ? `${it.center[0].toFixed(5)},${it.center[1].toFixed(5)},${Math.round(it.scale)}` : ""}`;
  const ovKey = (it: OverviewItem) => `${it.w.toFixed(1)}x${it.h.toFixed(1)}|${it.extent}|${it.zoomOut}|${it.mapId}|${caps[it.mapId]?.key ?? ""}|${outlines ? "o" : ""}`;
  const wanted = layout.items.filter((i) => i.visible && (i.type === "map" || i.type === "overview"))
    .map((i) => `${i.id}=${i.type === "map" ? mapKey(i) : ovKey(i as OverviewItem)}`).join(";");

  useEffect(() => {
    let live = true;
    const t = window.setTimeout(async () => {
      const todo = layout.items.filter((i) => i.visible && (i.type === "map" || i.type === "overview"));
      // Maps first: overviews outline their extent.
      todo.sort((a, b) => (a.type === "map" ? 0 : 1) - (b.type === "map" ? 0 : 1));
      const fresh: Record<string, MapImage & { key: string }> = {};
      for (const it of todo) {
        const key = it.type === "map" ? mapKey(it) : ovKey(it as OverviewItem);
        if (caps[it.id]?.key === key) continue;
        const cam = it.type === "map" ? cameraFor(it) : overviewCamera(it as OverviewItem, fresh[(it as OverviewItem).mapId] ?? caps[(it as OverviewItem).mapId]);
        if (!cam) continue;
        setCapturing((c) => c + 1);
        try {
          const cap = await captureMap(map, { widthMm: it.w, heightMm: it.h, dpi: PREVIEW_DPI, camera: cam });
          if (!live) return;
          const href = URL.createObjectURL(await new Promise<Blob>((ok) => cap.image.toBlob((b) => ok(b!), "image/png")));
          fresh[it.id] = { href, cap, key };
          setCaps((c) => { if (c[it.id]) URL.revokeObjectURL(c[it.id].href); return { ...c, [it.id]: fresh[it.id] }; });
          setOffsets((o) => { if (!o[it.id]) return o; const n = { ...o }; delete n[it.id]; return n; });
        } catch (e) {
          if (live) setError(e instanceof Error ? e.message : "The map couldn't be drawn.");
        } finally {
          setCapturing((c) => c - 1);
        }
      }
    }, 450);
    return () => { live = false; window.clearTimeout(t); };
  }, [wanted]);

  /* ---------------- pictures */
  const srcs = [...new Set(layout.items.filter((i): i is PictureItem => i.type === "picture").map((i) => i.src))].join("|");
  useEffect(() => {
    for (const src of srcs.split("|").filter(Boolean)) {
      if (pictures[src]) continue;
      loadPicture(src).then((p) => setPictures((all) => ({ ...all, [src]: p }))).catch(() => setError("A picture couldn't be loaded."));
    }
  }, [srcs]);

  /* ---------------- render */
  const mainScale = maps[0] && caps[maps[0].id] ? roundScale(scaleOf(caps[maps[0].id].cap, maps[0].w)) : 0;
  const vars: Vars = useMemo(() => ({
    title: context.title, subtitle: context.subtitle, code: context.code, country: context.country ?? "", author: context.author,
    date: new Date().toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" }),
    scale: mainScale ? `1:${mainScale.toLocaleString("en")}` : "",
    sources: sourcesLine(context.sources),
    crs: "WGS 84 / Pseudo-Mercator (EPSG:3857)",
  }), [context, mainScale]);
  // Globe locator: centred on the country, the project area as a marker.
  const mid = (b?: BBox | null): [number, number] | null => (b ? [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2] : null);
  const globeFocus = useMemo(() => {
    const center = mid(outlines?.country?.bbox ?? countryBbox) ?? mid(areaBbox);
    return center ? { center, gid: outlines?.country?.gid, name: context.country, marker: mid(areaBbox) } : undefined;
  }, [outlines, countryBbox, areaBbox, context.country]);
  const env: Env = { vars, legend, ramp, maps: caps, pictures, editing: true, offsets,
    outlines: { country: outlines?.country?.geometry, region: outlines?.region?.geometry },
    world, globe: globeFocus };
  const rendered = useMemo(() => renderLayout(layout, env), [layout, caps, pictures, vars, legend, ramp, offsets, outlines, world, globeFocus]);

  /* ---------------- editing helpers */
  const update = (id: string, patch: Partial<Item>, key = "") => commit((l) => ({ ...l, items: l.items.map((i) => (i.id === id ? ({ ...i, ...patch } as Item) : i)) }), key ? `${id}.${key}` : "");
  const setPage = (patch: Partial<Page>) => commit((l) => {
    const page = { ...l.page, ...patch };
    const a = pageSize(l.page), b = pageSize(page);
    return a.w === b.w && a.h === b.h ? { ...l, page } : fitToPage(l, page);
  }, "page");
  const remove = (id: string) => { commit((l) => ({ ...l, items: l.items.filter((i) => i.id !== id) })); setSel(null); };
  const duplicate = (id: string) => {
    const src = layout.items.find((i) => i.id === id);
    if (!src) return;
    const copy = { ...structuredClone(src), id: uid(src.type), name: `${src.name} copy`, x: src.x + 4, y: src.y + 4 } as Item;
    commit((l) => ({ ...l, items: [...l.items, copy] }));
    setSel(copy.id);
  };
  const reorder = (id: string, dir: 1 | -1 | "top" | "bottom") => commit((l) => {
    const items = [...l.items];
    const i = items.findIndex((x) => x.id === id);
    const [it] = items.splice(i, 1);
    const j = dir === "top" ? items.length : dir === "bottom" ? 0 : Math.max(0, Math.min(items.length, i + dir));
    items.splice(j, 0, it);
    return { ...l, items };
  });
  const add = (type: ItemType) => {
    const it = newItem(type, W / 2 - 20, H / 2 - 10, { mapId: maps[0]?.id, ramp });
    if (type === "map") Object.assign(it, { x: W * 0.25, y: H * 0.25, w: W * 0.5, h: H * 0.5 });
    commit((l) => ({ ...l, items: [...l.items, it] }));
    setSel(it.id);
  };
  const applyTemplate = (id: TemplateId) => {
    const t = TEMPLATES.find((x) => x.id === id)!;
    commit((l) => buildTemplate(id, { ...l.page, ...t.page }, ramp));
    setSel(null);
    setZoom("fit");
  };

  /* ---------------- keyboard */
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement).tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
      const mod = e.metaKey || e.ctrlKey;
      if (e.key === "Escape") { if (panMode) setPanMode(null); else if (sel) setSel(null); else if (!busy) onClose(); return; }
      if (typing) return;
      if (mod && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? h.redo() : h.undo(); return; }
      if (mod && e.key.toLowerCase() === "y") { e.preventDefault(); h.redo(); return; }
      if (!item) return;
      if (mod && e.key.toLowerCase() === "d") { e.preventDefault(); duplicate(item.id); return; }
      if ((e.key === "Delete" || e.key === "Backspace") && !item.locked) { e.preventDefault(); remove(item.id); return; }
      const step = e.shiftKey ? 5 : 1;
      const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (d && !item.locked) { e.preventDefault(); update(item.id, { x: item.x + d[0], y: item.y + d[1] }, "nudge"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  /* ---------------- pointer: move, resize, pan map content */
  const toMm = (e: { clientX: number; clientY: number }): [number, number] => {
    const r = svg.current!.getBoundingClientRect();
    return [((e.clientX - r.left) / r.width) * W, ((e.clientY - r.top) / r.height) * H];
  };
  function onItemDown(e: React.PointerEvent, it: Item, handle = "move") {
    e.stopPropagation();
    if (e.button !== 0) return;
    setSel(it.id);
    const box = rendered.boxes[it.id] ?? it;
    const pan = panMode === it.id && it.type === "map" && handle === "move";
    if (it.locked && !pan) return;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    drag.current = { id: it.id, handle, start: toMm(e), box: { x: box.x, y: box.y, w: box.w, h: box.h }, pan };
    if (!pan) begin();
  }
  function onPointerMove(e: React.PointerEvent) {
    const d = drag.current;
    if (!d) return;
    const [mx, my] = toMm(e);
    let dx = mx - d.start[0], dy = my - d.start[1];
    if (d.pan) { setOffsets((o) => ({ ...o, [d.id]: [dx, dy] })); return; }
    const b = { ...d.box };
    const thr = 6 / pxPerMm;
    const xs = snapTargets("x", d.id), ys = snapTargets("y", d.id);
    const hit: { x: number[]; y: number[] } = { x: [], y: [] };
    if (d.handle === "move") {
      b.x += dx; b.y += dy;
      if (snap && !e.altKey) {
        const sx = bestSnap([b.x, b.x + b.w / 2, b.x + b.w], xs, thr), sy = bestSnap([b.y, b.y + b.h / 2, b.y + b.h], ys, thr);
        if (sx) { b.x += sx.delta; hit.x.push(sx.at); }
        if (sy) { b.y += sy.delta; hit.y.push(sy.at); }
      }
    } else {
      const hd = d.handle;
      if (e.shiftKey && hd.length === 2) { const r = d.box.w / Math.max(0.1, d.box.h); if (Math.abs(dx) > Math.abs(dy) * r) dy = (hd === "ne" || hd === "sw" ? -dx : dx) / r; else dx = (hd === "ne" || hd === "sw" ? -dy : dy) * r; }
      if (hd.includes("e")) b.w = d.box.w + dx;
      if (hd.includes("s")) b.h = d.box.h + dy;
      if (hd.includes("w")) { b.x = d.box.x + dx; b.w = d.box.w - dx; }
      if (hd.includes("n")) { b.y = d.box.y + dy; b.h = d.box.h - dy; }
      if (snap && !e.altKey) {
        const ex = hd.includes("e") ? b.x + b.w : hd.includes("w") ? b.x : null;
        const ey = hd.includes("s") ? b.y + b.h : hd.includes("n") ? b.y : null;
        if (ex != null) { const s = bestSnap([ex], xs, thr); if (s) { if (hd.includes("e")) b.w += s.delta; else { b.x += s.delta; b.w -= s.delta; } hit.x.push(s.at); } }
        if (ey != null) { const s = bestSnap([ey], ys, thr); if (s) { if (hd.includes("s")) b.h += s.delta; else { b.y += s.delta; b.h -= s.delta; } hit.y.push(s.at); } }
      }
      const it = layout.items.find((i) => i.id === d.id);
      const minH = it?.type === "shape" && it.shape === "line" ? -1e6 : 2;
      b.w = Math.max(2, b.w); b.h = Math.max(minH, b.h);
    }
    setSnapLines(hit);
    transient((l) => ({ ...l, items: l.items.map((i) => (i.id === d.id ? ({ ...i, x: b.x, y: b.y, w: b.w, h: i.type === "legend" && i.auto && d.handle === "move" ? i.h : b.h } as Item) : i)) }));
  }
  function onPointerUp() {
    const d = drag.current;
    drag.current = null;
    setSnapLines({ x: [], y: [] });
    if (!d?.pan) return;
    const it = layout.items.find((i) => i.id === d.id) as MapItem | undefined;
    const c = caps[d.id];
    const off = offsets[d.id];
    if (!it || !c || !off) return;
    const p = projector(c.cap.bounds, it.w, it.h);
    const center: [number, number] = [p.lon(it.w / 2 - off[0]), p.lat(it.h / 2 - off[1])];
    commit((l) => ({ ...l, items: l.items.map((i) => (i.id === it.id ? { ...it, extent: "custom", center, scale: it.extent === "custom" ? it.scale : Math.round(scaleOf(c.cap, it.w)) } : i)) }));
  }
  function onWheel(e: React.WheelEvent) {
    if (panMode) {
      const it = layout.items.find((i) => i.id === panMode) as MapItem | undefined;
      const c = it && caps[it.id];
      if (!it || !c) return;
      const scale = it.extent === "custom" ? it.scale : Math.round(scaleOf(c.cap, it.w));
      const next = Math.max(500, roundScale(scale * (e.deltaY > 0 ? 1.25 : 0.8)));
      update(it.id, { extent: "custom", center: it.extent === "custom" ? it.center : c.cap.center, scale: next } as Partial<MapItem>, "zoom");
      return;
    }
    if (e.ctrlKey || e.metaKey) setZoom(Math.max(0.5, Math.min(12, pxPerMm * (e.deltaY > 0 ? 0.9 : 1.1))));
  }
  function snapTargets(axis: "x" | "y", skip: string) {
    const size = axis === "x" ? W : H, m = layout.page.margin;
    const t = [0, m, size / 2, size - m, size];
    for (const i of layout.items) {
      if (i.id === skip || !i.visible) continue;
      const b = rendered.boxes[i.id] ?? i;
      if (axis === "x") t.push(b.x, b.x + b.w / 2, b.x + b.w); else t.push(b.y, b.y + b.h / 2, b.y + b.h);
    }
    return t;
  }

  /* ---------------- export */
  const name = `${code}_map`;
  const realDpi = usableDpi(layout, dpi);
  async function full(outDpi: number) {
    const hi: Record<string, MapImage> = {};
    const order = layout.items.filter((i) => i.visible && (i.type === "map" || i.type === "overview"))
      .sort((a, b) => (a.type === "map" ? 0 : 1) - (b.type === "map" ? 0 : 1));
    for (const it of order) {
      const cam = it.type === "map" ? cameraFor(it) : overviewCamera(it as OverviewItem, hi[(it as OverviewItem).mapId]);
      if (!cam) continue;
      const cap = await captureMap(map, { widthMm: it.w, heightMm: it.h, dpi: outDpi, camera: cam });
      hi[it.id] = { cap, href: cap.image.toDataURL("image/png") };
    }
    const pics: Env["pictures"] = {};
    for (const [src, p] of Object.entries(pictures)) if (p) pics[src] = { ...p, href: p.href.startsWith("data:") ? p.href : await fetch(p.href).then((r) => r.blob()).then(toDataUrl) };
    return renderLayout(layout, { ...env, maps: hi, pictures: pics, editing: false });
  }
  async function run(label: string, fn: () => Promise<void>) {
    setBusy(label); setError(null);
    try { await embeddedFontCss(); await fn(); } catch (e) { setError(e instanceof Error ? e.message : "Export failed."); } finally { setBusy(null); }
  }

  /* ---------------- view */
  const pagePx = { w: W * pxPerMm, h: H * pxPerMm };
  const handles = ["nw", "n", "ne", "e", "se", "s", "sw", "w"];
  const selBox = item ? (rendered.boxes[item.id] ?? item) : null;

  return createPortal(
    <div className="ple" role="dialog" aria-modal="true" aria-labelledby="ple-title">
      <header className="ple-bar">
        <h2 id="ple-title"><LayoutTemplate aria-hidden="true" />Map layout</h2>
        <span className="muted small">{code} · {PAPERS.find((p) => p.id === layout.page.paper)?.label} {layout.page.paper !== "custom" ? layout.page.orientation : ""} · {Math.round(W)} × {Math.round(H)} mm</span>
        <div className="ple-tools">
          <ToolBtn label="Undo (Ctrl+Z)" disabled={!h.canUndo} onClick={h.undo}><Undo2 /></ToolBtn>
          <ToolBtn label="Redo (Ctrl+Shift+Z)" disabled={!h.canRedo} onClick={h.redo}><Redo2 /></ToolBtn>
          <span className="ple-sep" />
          <ToolBtn label="Zoom out" onClick={() => setZoom(Math.max(0.5, pxPerMm / 1.25))}><ZoomOut /></ToolBtn>
          <button type="button" className="ple-zoom" title="Fit page" onClick={() => setZoom("fit")}>{Math.round((pxPerMm / MM_TO_CSS) * 100)}%</button>
          <ToolBtn label="Zoom in" onClick={() => setZoom(Math.min(12, pxPerMm * 1.25))}><ZoomIn /></ToolBtn>
          <ToolBtn label="Fit page" onClick={() => setZoom("fit")}><Maximize /></ToolBtn>
          <span className="ple-sep" />
          <ToolBtn label="Snap to guides and items (hold Alt to place freely)" active={snap} onClick={() => setSnap((v) => !v)}><Magnet /></ToolBtn>
          <ToolBtn label="Show margins and centre guides" active={guides} onClick={() => setGuides((v) => !v)}><Grid3x3 /></ToolBtn>
          {item?.type === "map" && <ToolBtn label="Move map content: drag to pan, scroll to zoom (or double-click the map)" active={panMode === item.id} onClick={() => setPanMode(panMode === item.id ? null : item.id)}><Move /></ToolBtn>}
        </div>
        <button type="button" className="icon-btn" aria-label="Close" onClick={onClose} disabled={!!busy}><X aria-hidden="true" /></button>
      </header>

      <div className="ple-body">
        {/* ----------------------------------------------------- left: templates, add, items */}
        <aside className="ple-left">
          <Section title="Templates" open>
            <div className="ple-templates">
              {TEMPLATES.map((t) => (
                <button key={t.id} type="button" className={`ple-tpl${layout.template === t.id ? " is-on" : ""}`} title={t.desc}
                  onClick={async () => { if (await confirm({ title: `Use the ${t.label} template?`, message: "It replaces the items on this page. You can undo with Ctrl+Z.", confirmLabel: "Use template" })) applyTemplate(t.id); }}>
                  <TemplateThumb id={t.id} /><span>{t.label}</span>
                </button>
              ))}
            </div>
            <SavedTemplates templates={templates} onApply={async (t) => { if (await confirm({ title: `Load "${t.name}"?`, message: "It replaces this layout. You can undo with Ctrl+Z.", confirmLabel: "Load template" })) { commit(() => instantiate(t.layout)); setSel(null); setZoom("fit"); } }}
              onDelete={async (t) => { if (await confirm({ title: `Delete the template "${t.name}"?`, message: "Layouts already made from it aren't affected.", confirmLabel: "Delete", tone: "danger" })) { deleteTemplate(t.name); setTemplates(listTemplates()); } }}
              onSave={(n) => { try { storeTemplate(n, { ...layout, template: n }); setTemplates(listTemplates()); } catch (e) { setError((e as Error).message); } }} />
          </Section>
          <Section title="Add item" open>
            <div className="ple-add">
              {ADDABLE.map(({ type, icon: Icon }) => (
                <button key={type} type="button" onClick={() => add(type)} disabled={(type === "overview" || type === "scalebar") && !maps.length}>
                  <Icon aria-hidden="true" /><span>{ITEM_LABEL[type]}</span>
                </button>
              ))}
            </div>
          </Section>
          <Section title={`Items (${layout.items.length})`} open grow>
            <ul className="ple-items">
              {[...layout.items].reverse().map((it) => {
                const Icon = ICON[it.type];
                return (
                  <li key={it.id} className={sel === it.id ? "is-sel" : ""}>
                    <button type="button" className="ple-vis" aria-label={it.visible ? `Hide ${it.name}` : `Show ${it.name}`} onClick={() => update(it.id, { visible: !it.visible })}>{it.visible ? <Eye /> : <EyeOff />}</button>
                    <button type="button" className="ple-vis" aria-label={it.locked ? `Unlock ${it.name}` : `Lock ${it.name}`} onClick={() => update(it.id, { locked: !it.locked })}>{it.locked ? <Lock /> : <LockOpen className="is-faint" />}</button>
                    <button type="button" className="ple-item-name" onClick={() => setSel(it.id)}><Icon aria-hidden="true" /><span>{it.name}</span></button>
                  </li>
                );
              })}
            </ul>
          </Section>
        </aside>

        {/* ----------------------------------------------------- centre: the page */}
        <div className="ple-stage">
        <div className="ple-canvas" ref={canvasEl} onWheel={onWheel} onPointerDown={() => { setSel(null); setPanMode(null); }}>
          <div className="ple-scroll" style={{ minWidth: pagePx.w + 64, minHeight: pagePx.h + 64 }}>
            <svg ref={svg} className="ple-page" width={pagePx.w} height={pagePx.h} viewBox={`0 0 ${W} ${H}`}
              onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerCancel={onPointerUp}>
              <g dangerouslySetInnerHTML={{ __html: `<defs>${rendered.defs}</defs>${rendered.body}` }} />
              {guides && (
                <g className="ple-guides" pointerEvents="none">
                  <rect x={layout.page.margin} y={layout.page.margin} width={W - 2 * layout.page.margin} height={H - 2 * layout.page.margin} />
                </g>
              )}
              <g className="ple-hits">
                {layout.items.map((it) => {
                  if (!it.visible) return null;
                  const b = rendered.boxes[it.id] ?? it;
                  const pad = it.type === "shape" && it.shape === "line" ? 1.2 : 0;
                  return (
                    <rect key={it.id} x={Math.min(b.x, b.x + b.w) - pad} y={Math.min(b.y, b.y + b.h) - pad} width={Math.abs(b.w) + 2 * pad} height={Math.abs(b.h) + 2 * pad}
                      className={`${it.locked ? "is-locked" : ""}${panMode === it.id ? " is-pan" : ""}`}
                      onPointerDown={(e) => onItemDown(e, it)} onDoubleClick={() => it.type === "map" && setPanMode(panMode === it.id ? null : it.id)} />
                  );
                })}
              </g>
              {snapLines.x.map((x, i) => <line key={`x${i}`} className="ple-snap" x1={x} x2={x} y1={0} y2={H} />)}
              {snapLines.y.map((y, i) => <line key={`y${i}`} className="ple-snap" y1={y} y2={y} x1={0} x2={W} />)}
              {item && selBox && item.visible && (
                <g className={`ple-sel${panMode === item.id ? " is-pan" : ""}`}>
                  <rect x={Math.min(selBox.x, selBox.x + selBox.w)} y={Math.min(selBox.y, selBox.y + selBox.h)} width={Math.abs(selBox.w)} height={Math.max(0.01, Math.abs(selBox.h))} strokeWidth={1.2 / pxPerMm} />
                  {!item.locked && panMode !== item.id && !(item.type === "legend" && item.auto) && handles.map((hd) => {
                    const hs = 7 / pxPerMm;
                    const hx = selBox.x + (hd.includes("w") ? 0 : hd.includes("e") ? selBox.w : selBox.w / 2);
                    const hy = selBox.y + (hd.includes("n") ? 0 : hd.includes("s") ? selBox.h : selBox.h / 2);
                    return <rect key={hd} className={`ple-handle h-${hd}`} x={hx - hs / 2} y={hy - hs / 2} width={hs} height={hs} strokeWidth={1 / pxPerMm} onPointerDown={(e) => onItemDown(e, item, hd)} />;
                  })}
                </g>
              )}
            </svg>
          </div>
        </div>
          {capturing > 0 && <span className="ple-status"><LoaderCircle className="spin" aria-hidden="true" />Drawing map…</span>}
          {panMode && <span className="ple-status ple-status-pan"><Move aria-hidden="true" />Drag to pan, scroll to zoom the map · Esc to finish</span>}
          {error && <p className="ple-error" role="alert">{error}<button type="button" className="icon-btn icon-btn-xs" aria-label="Dismiss" onClick={() => setError(null)}><X /></button></p>}
        </div>

        {/* ----------------------------------------------------- right: properties */}
        <aside className="ple-right">
          {item ? (
            <ItemProps key={item.id} it={item} layout={layout} legend={legend} ramp={ramp} caps={caps} pictures={pictures} areaBbox={areaBbox} countryBbox={countryBbox} outlines={outlines}
              update={(p, k) => update(item.id, p, k)} onDelete={() => remove(item.id)} onDuplicate={() => duplicate(item.id)} onOrder={(d) => reorder(item.id, d)}
              onError={setError} onPan={() => setPanMode(panMode === item.id ? null : item.id)} panning={panMode === item.id} />
          ) : (
            <PageProps page={layout.page} set={setPage} />
          )}
        </aside>
      </div>

      <footer className="ple-foot">
        <label className="ple-dpi">Resolution
          <select className="input" value={dpi} onChange={(e) => setDpi(Number(e.target.value))}>
            {DPIS.map((d) => <option key={d} value={d}>{d} dpi{d === 300 ? " (print)" : d === 600 ? " (publication)" : " (screen)"}</option>)}
          </select>
        </label>
        {realDpi < dpi && <span className="muted small">This page size exports at {realDpi} dpi (browser limit).</span>}
        <span className="ple-foot-gap" />
        <span className="muted small ple-hint">SVG keeps text and symbols as vectors (edit in Illustrator or Inkscape).</span>
        <button type="button" className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => run("copy", async () => copyPng(await full(150)))}><Copy aria-hidden="true" />{busy === "copy" ? "Copying…" : "Copy"}</button>
        <button type="button" className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => run("print", async () => printPage(await full(Math.min(realDpi, 300)), Math.min(realDpi, 300), context.title))}><Printer aria-hidden="true" />{busy === "print" ? "Preparing…" : "Print"}</button>
        <button type="button" className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => run("svg", async () => exportSvg(await full(Math.min(realDpi, 300)), name))}><FileCode aria-hidden="true" />{busy === "svg" ? "Exporting…" : "SVG"}</button>
        <button type="button" className="btn btn-outline btn-sm" disabled={!!busy} onClick={() => run("png", async () => exportPng(await full(realDpi), realDpi, name))}><FileImage aria-hidden="true" />{busy === "png" ? "Exporting…" : "PNG"}</button>
        <button type="button" className="btn btn-dark btn-sm" disabled={!!busy} onClick={() => run("pdf", async () => exportPdf(await full(realDpi), realDpi, name, { title: context.title, subject: context.subtitle }))}><FileText aria-hidden="true" />{busy === "pdf" ? "Exporting…" : "PDF"}</button>
      </footer>
    </div>,
    document.body,
  );
}

function sourcesLine(sources: string[]) {
  const unique = [...new Set(sources.map((s) => s.trim()).filter(Boolean))];
  return unique.length ? `Sources: ${unique.join("; ")}.` : "";
}

function bestSnap(edges: number[], targets: number[], thr: number) {
  let best: { delta: number; at: number } | null = null;
  for (const e of edges) for (const t of targets) {
    const d = t - e;
    if (Math.abs(d) <= thr && (!best || Math.abs(d) < Math.abs(best.delta))) best = { delta: d, at: t };
  }
  return best;
}

/* ------------------------------------------------------------------ left panel parts */

function TemplateThumb({ id }: { id: TemplateId }) {
  const portrait = id === "report";
  const [w, h] = portrait ? [30, 42] : [42, 30];
  const blocks: Record<TemplateId, [number, number, number, number, string][]> = {
    classic: [[2, 2, 28, 3, "t"], [34, 2, 6, 3, "l"], [2, 7, 28, 19, "m"], [32, 7, 8, 7, "o"], [32, 16, 8, 6, "g"], [2, 27, 38, 1, "f"]],
    report: [[2, 2, 20, 3, "t"], [23, 2, 5, 3, "l"], [2, 7, 26, 18, "m"], [2, 27, 12, 8, "g"], [16, 27, 12, 8, "o"], [2, 37, 26, 3, "f"]],
    poster: [[2, 2, 28, 4, "t"], [34, 2, 6, 4, "l"], [2, 8, 26, 19, "m"], [30, 8, 10, 8, "o"], [30, 18, 10, 7, "g"], [2, 28, 38, 1, "f"]],
    clean: [[2, 2, 38, 26, "m"], [4, 4, 14, 4, "t"], [30, 18, 8, 8, "g"], [4, 24, 10, 2, "f"]],
  };
  const fill: Record<string, string> = { t: "#0b3b47", l: "#c9a25b", m: "#b9d3d9", o: "#dfe7ea", g: "#ffffff", f: "#9ca3af" };
  return (
    <svg viewBox={`0 0 ${w} ${h}`} width={w * 1.3} height={h * 1.3} aria-hidden="true">
      <rect x="0.5" y="0.5" width={w - 1} height={h - 1} fill="#fff" stroke="#cbd2d6" />
      {blocks[id].map(([x, y, bw, bh, k], i) => <rect key={i} x={x} y={y} width={bw} height={bh} fill={fill[k]} stroke={k === "g" ? "#9ca3af" : "none"} strokeWidth="0.4" />)}
    </svg>
  );
}

function SavedTemplates({ templates, onApply, onDelete, onSave }: {
  templates: SavedTemplate[]; onApply: (t: SavedTemplate) => void; onDelete: (t: SavedTemplate) => void; onSave: (name: string) => void;
}) {
  const [name, setName] = useState("");
  return (
    <div className="ple-saved">
      <form className="ple-save" onSubmit={(e) => { e.preventDefault(); if (name.trim()) { onSave(name.trim()); setName(""); } }}>
        <input className="input" placeholder="Save this layout as a template…" value={name} onChange={(e) => setName(e.target.value)} aria-label="Template name" />
        <button type="submit" className="icon-btn" aria-label="Save template" title="Save as template" disabled={!name.trim()}><Save aria-hidden="true" /></button>
      </form>
      {templates.length > 0 && (
        <ul>
          {templates.map((t) => (
            <li key={t.name}>
              <button type="button" className="link-btn" onClick={() => onApply(t)}>{t.name}</button>
              <span className="muted small">{new Date(t.saved).toLocaleDateString()}</span>
              <button type="button" className="icon-btn icon-btn-xs" aria-label={`Delete template ${t.name}`} onClick={() => onDelete(t)}><Trash2 aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ page properties */

function PageProps({ page, set }: { page: Page; set: (p: Partial<Page>) => void }) {
  return (
    <div className="ple-props">
      <h3>Page</h3>
      <p className="muted small">Select an item on the page to edit it. Changing the paper size stretches the layout to fit.</p>
      <Row label="Paper">
        <select className="input" value={page.paper} onChange={(e) => set({ paper: e.target.value as Page["paper"] })}>
          {PAPERS.map((p) => <option key={p.id} value={p.id}>{p.label}{p.id !== "custom" ? ` (${Math.min(p.w, p.h)} × ${Math.max(p.w, p.h)} mm)` : ""}</option>)}
        </select>
      </Row>
      {page.paper === "custom" ? (
        <div className="ple-grid2">
          <Num label="Width (mm)" value={page.custom.w} min={50} onChange={(w) => set({ custom: { ...page.custom, w } })} />
          <Num label="Height (mm)" value={page.custom.h} min={50} onChange={(h) => set({ custom: { ...page.custom, h } })} />
        </div>
      ) : (
        <Seg label="Orientation" value={page.orientation} options={[["landscape", "Landscape"], ["portrait", "Portrait"]]} onChange={(orientation) => set({ orientation })} />
      )}
      <div className="ple-grid2">
        <Color label="Background" value={page.background} onChange={(background) => set({ background })} />
        <Num label="Margin guides (mm)" value={page.margin} min={0} onChange={(margin) => set({ margin })} />
      </div>
      <Check label="Page border" checked={page.border.show} onChange={(show) => set({ border: { ...page.border, show } })} />
      {page.border.show && (
        <div className="ple-grid2">
          <Color label="Colour" value={page.border.color} onChange={(color) => set({ border: { ...page.border, color } })} />
          <Num label="Width (mm)" value={page.border.width} min={0.1} step={0.1} onChange={(width) => set({ border: { ...page.border, width } })} />
        </div>
      )}
      <h3>Shortcuts</h3>
      <ul className="ple-keys">
        <li><kbd>Drag</kbd> move · handles resize · <kbd>Shift</kbd> keep proportions · <kbd>Alt</kbd> no snapping</li>
        <li><kbd>Arrows</kbd> nudge 1 mm (<kbd>Shift</kbd> 5 mm)</li>
        <li><kbd>Ctrl/⌘ Z</kbd> undo · <kbd>Ctrl/⌘ D</kbd> duplicate · <kbd>Delete</kbd> remove</li>
        <li><kbd>Double-click</kbd> a map to pan and zoom its content · <kbd>Ctrl/⌘ scroll</kbd> zoom the page</li>
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ item properties */

type PropsArgs = {
  it: Item; layout: Layout; legend: LegendEntry[]; ramp: Ramp | null; caps: Record<string, MapImage>;
  pictures: Env["pictures"]; areaBbox?: BBox | null; countryBbox?: BBox | null; outlines?: Outlines | null;
  update: (p: Partial<Item>, key?: string) => void; onDelete: () => void; onDuplicate: () => void;
  onOrder: (d: 1 | -1 | "top" | "bottom") => void; onError: (m: string) => void; onPan: () => void; panning: boolean;
};

function ItemProps(a: PropsArgs) {
  const { it, update } = a;
  const Icon = ICON[it.type];
  return (
    <div className="ple-props">
      <div className="ple-props-head">
        <Icon aria-hidden="true" />
        <input className="input" value={it.name} onChange={(e) => update({ name: e.target.value }, "name")} aria-label="Item name" />
      </div>
      <div className="ple-props-actions">
        <ToolBtn label="Bring to front" onClick={() => a.onOrder("top")}><ArrowUp /></ToolBtn>
        <ToolBtn label="Raise" onClick={() => a.onOrder(1)}><ArrowUp className="is-faint" /></ToolBtn>
        <ToolBtn label="Lower" onClick={() => a.onOrder(-1)}><ArrowDown className="is-faint" /></ToolBtn>
        <ToolBtn label="Send to back" onClick={() => a.onOrder("bottom")}><ArrowDown /></ToolBtn>
        <span className="ple-sep" />
        <ToolBtn label="Duplicate (Ctrl+D)" onClick={a.onDuplicate}><Copy /></ToolBtn>
        <ToolBtn label="Delete" onClick={a.onDelete} disabled={it.locked}><Trash2 /></ToolBtn>
      </div>

      <Section title="Position and size" open>
        <div className="ple-grid4">
          <Num label="X" value={it.x} step={0.5} onChange={(x) => update({ x }, "x")} />
          <Num label="Y" value={it.y} step={0.5} onChange={(y) => update({ y }, "y")} />
          <Num label="W" value={it.w} step={0.5} min={it.type === "shape" ? -1000 : 2} onChange={(w) => update({ w }, "w")} />
          <Num label="H" value={it.h} step={0.5} min={it.type === "shape" ? -1000 : 2} onChange={(h) => update({ h }, "h")} />
        </div>
        <p className="muted small ple-note">Millimetres from the page's top-left corner.</p>
      </Section>

      {it.type === "map" && <MapProps {...a} it={it} />}
      {it.type === "overview" && <OverviewProps {...a} it={it} />}
      {it.type === "text" && <TextProps it={it} update={update} />}
      {it.type === "legend" && <LegendProps it={it} update={update} legend={a.legend} />}
      {it.type === "scalebar" && <ScaleBarProps it={it} update={update} layout={a.layout} />}
      {it.type === "north" && <NorthProps it={it} update={update} />}
      {it.type === "colorbar" && <ColorbarProps it={it} update={update} ramp={a.ramp} />}
      {it.type === "picture" && <PictureProps it={it} update={update} onError={a.onError} />}
      {it.type === "shape" && <ShapeProps it={it} update={update} />}

      {it.type !== "shape" && (
        <Section title="Frame and background">
          <FrameEdit frame={it.frame} onChange={(frame) => update({ frame }, "frame")} isMap={it.type === "map" || it.type === "overview"} />
        </Section>
      )}
    </div>
  );
}

function MapProps({ it, update, caps, areaBbox, onPan, panning }: PropsArgs & { it: MapItem }) {
  const c = caps[it.id];
  const scaleNow = c ? roundScale(scaleOf(c.cap, it.w)) : 0;
  const set = (p: Partial<MapItem>, k?: string) => update(p, k);
  const custom = (scale: number) => set({ extent: "custom", center: it.extent === "custom" ? it.center : c?.cap.center ?? it.center, scale: Math.max(500, roundScale(scale)) }, "scale");
  const g = it.grid;
  const setGrid = (p: Partial<MapItem["grid"]>) => set({ grid: { ...g, ...p } }, "grid");
  return (
    <>
      <Section title="Extent and scale" open>
        <Seg value={it.extent} options={[["view", "Project map view"], ...(areaBbox ? [["area", "Project area"] as ["area", string]] : []), ["custom", "Set here"]]}
          onChange={(extent) => set(extent === "custom" ? { extent, center: c?.cap.center ?? it.center, scale: scaleNow || it.scale } : { extent })} />
        <Row label="Scale 1:">
          <input className="input" type="number" min={500} step={1000} value={it.extent === "custom" ? it.scale : scaleNow || ""} placeholder="…"
            onChange={(e) => set({ extent: "custom", center: it.extent === "custom" ? it.center : c?.cap.center ?? it.center, scale: Math.max(500, Math.round(Number(e.target.value) || 500)) }, "scale")} />
        </Row>
        <div className="ple-btnrow">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => custom((it.extent === "custom" ? it.scale : scaleNow) / 1.5)}><ZoomIn aria-hidden="true" />Zoom in</button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => custom((it.extent === "custom" ? it.scale : scaleNow) * 1.5)}><ZoomOut aria-hidden="true" />Zoom out</button>
          <button type="button" className={`btn btn-sm ${panning ? "btn-dark" : "btn-outline"}`} onClick={onPan}><Move aria-hidden="true" />{panning ? "Done" : "Pan"}</button>
        </div>
        <p className="muted small ple-note">Tip: double-click the map on the page, then drag to pan and scroll to zoom.</p>
      </Section>
      <Section title="Grid (graticule)">
        <Check label="Show coordinate grid" checked={g.show} onChange={(show) => setGrid({ show })} />
        {g.show && (
          <>
            <div className="ple-grid2">
              <Row label="Interval">
                <select className="input" value={g.interval} onChange={(e) => setGrid({ interval: Number(e.target.value) })}>
                  <option value={0}>Automatic</option>
                  {[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10].map((v) => <option key={v} value={v}>{v < 1 ? `${Math.round(v * 60 * 100) / 100}′ (${v}°)` : `${v}°`}</option>)}
                </select>
              </Row>
              <Row label="Style">
                <select className="input" value={g.style} onChange={(e) => setGrid({ style: e.target.value as MapItem["grid"]["style"] })}>
                  <option value="lines">Lines</option><option value="crosses">Crosses</option>
                </select>
              </Row>
            </div>
            <Seg label="Labels" value={g.labels} options={[["outside", "Outside"], ["inside", "Inside"], ["none", "None"]]} onChange={(labels) => setGrid({ labels })} />
            <Seg label="Format" value={g.format} options={[["dms", "34°30′E"], ["decimal", "34.5°E"]]} onChange={(format) => setGrid({ format })} />
            {g.labels === "outside" && <Check label="Zebra border" checked={g.zebra} onChange={(zebra) => setGrid({ zebra })} />}
            <div className="ple-grid3">
              <Color label="Colour" value={g.color} onChange={(color) => setGrid({ color })} />
              <Num label="Line (mm)" value={g.width} min={0.05} step={0.05} onChange={(width) => setGrid({ width })} />
              <Num label="Labels (pt)" value={g.labelSize} min={4} step={0.5} onChange={(labelSize) => setGrid({ labelSize })} />
            </div>
          </>
        )}
      </Section>
    </>
  );
}

function OverviewProps({ it, update, layout, countryBbox, outlines }: PropsArgs & { it: OverviewItem }) {
  const maps = layout.items.filter((i) => i.type === "map");
  return (
    <Section title="Overview" open>
      <Row label="Shows the extent of">
        <select className="input" value={it.mapId} onChange={(e) => update({ mapId: e.target.value } as Partial<OverviewItem>)}>
          {maps.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </Row>
      <Seg label="Area shown" value={it.extent}
        options={[
          ...(countryBbox || outlines?.country ? [["country", outlines?.country?.name ?? "Country"] as ["country", string]] : []),
          ...(outlines?.region ? [["region", outlines.region.name] as ["region", string]] : []),
          ["around", "Around the map"],
          ["globe", "Globe"],
        ]}
        onChange={(extent) => update({ extent } as Partial<OverviewItem>)} />
      {it.extent === "globe" && <GlobeProps it={it} update={update} />}
      {it.extent === "around" && <Num label="Zoomed out ×" value={it.zoomOut} min={1.5} step={0.5} onChange={(zoomOut) => update({ zoomOut } as Partial<OverviewItem>, "zoomOut")} />}
      {it.extent === "globe" ? (
        <div className="ple-grid2">
          <Color label="Area marker" value={it.boxColor} onChange={(boxColor) => update({ boxColor } as Partial<OverviewItem>, "box")} />
          <Num label="Outline (mm)" value={it.outlineWidth ?? 0.35} min={0.1} step={0.05} onChange={(outlineWidth) => update({ outlineWidth } as Partial<OverviewItem>, "outline")} />
        </div>
      ) : (
        <div className="ple-grid2">
          <Color label="Extent box" value={it.boxColor} onChange={(boxColor) => update({ boxColor } as Partial<OverviewItem>, "box")} />
          <Num label="Line (mm)" value={it.boxWidth} min={0.1} step={0.1} onChange={(boxWidth) => update({ boxWidth } as Partial<OverviewItem>, "box")} />
        </div>
      )}
      {it.extent !== "globe" && <Check label={it.extent === "region" ? "Country and region boundaries" : "Country boundary"} checked={it.outline !== false} onChange={(outline) => update({ outline } as Partial<OverviewItem>)} />}
      {it.extent !== "globe" && it.outline !== false && (
        <div className="ple-grid2">
          <Color label="Boundary" value={it.outlineColor ?? "#0B3B47"} onChange={(outlineColor) => update({ outlineColor } as Partial<OverviewItem>, "outline")} />
          <Num label="Line (mm)" value={it.outlineWidth ?? 0.35} min={0.1} step={0.05} onChange={(outlineWidth) => update({ outlineWidth } as Partial<OverviewItem>, "outline")} />
        </div>
      )}
      {outlines && !outlines.country && <p className="muted small">No boundary found for this country.</p>}
    </Section>
  );
}

function GlobeProps({ it, update }: { it: OverviewItem; update: PropsArgs["update"] }) {
  const g = { ...DEFAULT_GLOBE, ...it.globe };
  const set = (p: Partial<typeof g>) => update({ globe: { ...g, ...p } } as Partial<OverviewItem>, "globe");
  return (
    <>
      <div className="ple-grid2">
        <Color label="Country" value={g.highlight} onChange={(highlight) => set({ highlight })} />
        <Color label="Other land" value={g.land} onChange={(land) => set({ land })} />
        <Color label="Ocean" value={g.ocean} onChange={(ocean) => set({ ocean })} />
        <Color label="Borders" value={g.border} onChange={(border) => set({ border })} />
      </div>
      <Check label="Graticule (30° lines)" checked={g.graticule} onChange={(graticule) => set({ graticule })} />
      <Check label="Mark the project area" checked={g.marker !== false} onChange={(marker) => set({ marker })} />
      <p className="muted small">Drawn as vectors from simplified country outlines: sharp at any size, editable in SVG.</p>
    </>
  );
}

function TextProps({ it, update }: { it: TextItem; update: PropsArgs["update"] }) {
  const ta = useRef<HTMLTextAreaElement>(null);
  const insert = (v: string) => {
    const el = ta.current;
    const at = el ? el.selectionStart : it.text.length;
    update({ text: `${it.text.slice(0, at)}{${v}}${it.text.slice(at)}` } as Partial<TextItem>);
  };
  return (
    <Section title="Text" open>
      <textarea ref={ta} className="input" rows={4} value={it.text} onChange={(e) => update({ text: e.target.value } as Partial<TextItem>, "text")} aria-label="Text" />
      <Row label="Insert a field">
        <select className="input" value="" onChange={(e) => e.target.value && insert(e.target.value)}>
          <option value="">Project title, date, scale…</option>
          {VARIABLES.map((v) => <option key={v} value={v}>{`{${v}}`}</option>)}
        </select>
      </Row>
      <FontEdit value={it.font} onChange={(font) => update({ font } as Partial<TextItem>, "font")} />
      <Seg label="Align" value={it.align} options={[["left", "Left"], ["center", "Centre"], ["right", "Right"]]} onChange={(align) => update({ align } as Partial<TextItem>)} />
      <Seg label="Vertical" value={it.valign} options={[["top", "Top"], ["middle", "Middle"], ["bottom", "Bottom"]]} onChange={(valign) => update({ valign } as Partial<TextItem>)} />
      <div className="ple-grid2">
        <Num label="Line spacing" value={it.lineHeight} min={0.8} step={0.05} onChange={(lineHeight) => update({ lineHeight } as Partial<TextItem>, "lh")} />
        <div className="ple-row"><span>&nbsp;</span><Check label="White halo" checked={it.halo} onChange={(halo) => update({ halo } as Partial<TextItem>)} /></div>
      </div>
    </Section>
  );
}

function LegendProps({ it, update, legend }: { it: LegendItem; update: PropsArgs["update"]; legend: LegendEntry[] }) {
  const set = (p: Partial<LegendItem>, k?: string) => update(p, k);
  return (
    <>
      <Section title="Legend" open>
        <Row label="Title"><input className="input" value={it.title} onChange={(e) => set({ title: e.target.value }, "title")} /></Row>
        <Check label="Fit the box to its contents" checked={it.auto} onChange={(auto) => set({ auto })} />
        <div className="ple-grid3">
          <Num label="Columns" value={it.columns} min={1} max={4} onChange={(columns) => set({ columns })} />
          <Num label="Symbol W" value={it.symbolW} min={1} step={0.5} onChange={(symbolW) => set({ symbolW }, "sym")} />
          <Num label="Symbol H" value={it.symbolH} min={1} step={0.5} onChange={(symbolH) => set({ symbolH }, "sym")} />
        </div>
        <ul className="ple-legend">
          {legend.map((e) => {
            const edit = it.edits[e.id] ?? {};
            const put = (p: { name?: string; hidden?: boolean }) => set({ edits: { ...it.edits, [e.id]: { ...edit, ...p } } }, `edit-${e.id}`);
            return (
              <li key={e.id}>
                <input type="checkbox" checked={!edit.hidden} aria-label={`Show ${e.name}`} onChange={(ev) => put({ hidden: !ev.target.checked })} />
                <i style={{ background: e.swatches[0]?.color }} />
                <input className="input" value={edit.name ?? e.name} aria-label="Legend label" onChange={(ev) => put({ name: ev.target.value })} disabled={edit.hidden} />
              </li>
            );
          })}
          {legend.length === 0 && <li className="muted small">No layers on the map yet.</li>}
        </ul>
      </Section>
      <Section title="Fonts">
        <p className="ple-sub">Title</p>
        <FontEdit value={it.titleFont} onChange={(titleFont) => set({ titleFont }, "tf")} />
        <p className="ple-sub">Labels</p>
        <FontEdit value={it.labelFont} onChange={(labelFont) => set({ labelFont }, "lf")} />
      </Section>
    </>
  );
}

function ScaleBarProps({ it, update, layout }: { it: ScaleBarItem; update: PropsArgs["update"]; layout: Layout }) {
  const set = (p: Partial<ScaleBarItem>, k?: string) => update(p, k);
  const maps = layout.items.filter((i) => i.type === "map");
  return (
    <Section title="Scale bar" open>
      <Row label="Map">
        <select className="input" value={it.mapId} onChange={(e) => set({ mapId: e.target.value })}>
          {maps.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </Row>
      <Row label="Style">
        <div className="ple-styles">
          {(["single", "double", "line", "hollow"] as const).map((s) => (
            <button key={s} type="button" className={it.style === s ? "is-on" : ""} onClick={() => set({ style: s })} title={s}>
              <svg viewBox="0 0 40 8" width="52" height="11" aria-hidden="true"><ScaleThumb style={s} /></svg>
            </button>
          ))}
        </div>
      </Row>
      <div className="ple-grid3">
        <Row label="Units">
          <select className="input" value={it.units} onChange={(e) => set({ units: e.target.value as ScaleBarItem["units"] })}>
            <option value="km">km</option><option value="m">m</option><option value="mi">miles</option>
          </select>
        </Row>
        <Num label="Segments" value={it.segments} min={1} max={10} onChange={(segments) => set({ segments })} />
        <Num label="Bar (mm)" value={it.barHeight} min={0.5} step={0.2} onChange={(barHeight) => set({ barHeight }, "bh")} />
      </div>
      <div className="ple-grid2">
        <Color label="Colour" value={it.color} onChange={(color) => set({ color }, "color")} />
        <Num label="Text (pt)" value={it.font.size} min={4} step={0.5} onChange={(size) => set({ font: { ...it.font, size } }, "fs")} />
      </div>
      <Check label='Show "Scale 1:50,000"' checked={it.showRatio} onChange={(showRatio) => set({ showRatio })} />
      <p className="muted small ple-note">The bar picks a round length that fits the box; widen the box for a longer bar.</p>
    </Section>
  );
}

function ScaleThumb({ style }: { style: ScaleBarItem["style"] }) {
  const c = "#1f2937";
  if (style === "line") return <><line x1="2" y1="6" x2="38" y2="6" stroke={c} /><line x1="2" y1="2" x2="2" y2="6" stroke={c} /><line x1="20" y1="4" x2="20" y2="6" stroke={c} /><line x1="38" y1="2" x2="38" y2="6" stroke={c} /></>;
  const segs = [0, 1, 2, 3];
  return (
    <>
      {segs.map((i) => style === "double"
        ? <g key={i}><rect x={2 + i * 9} y="1" width="9" height="3" fill={i % 2 ? "#fff" : c} /><rect x={2 + i * 9} y="4" width="9" height="3" fill={i % 2 ? c : "#fff"} /></g>
        : <rect key={i} x={2 + i * 9} y="1" width="9" height="6" fill={style === "hollow" ? "#fff" : i % 2 ? "#fff" : c} stroke={style === "hollow" ? c : "none"} strokeWidth="0.6" />)}
      <rect x="2" y="1" width="36" height="6" fill="none" stroke={c} strokeWidth="0.8" />
    </>
  );
}

function NorthProps({ it, update }: { it: NorthItem; update: PropsArgs["update"] }) {
  return (
    <Section title="North arrow" open>
      <Seg label="Style" value={it.style} options={[["arrow", "Arrow"], ["star", "Compass"], ["simple", "Simple"]]} onChange={(style) => update({ style } as Partial<NorthItem>)} />
      <Color label="Colour" value={it.color} onChange={(color) => update({ color } as Partial<NorthItem>, "color")} />
    </Section>
  );
}

function ColorbarProps({ it, update, ramp }: { it: ColorbarItem; update: PropsArgs["update"]; ramp: Ramp | null }) {
  const set = (p: Partial<ColorbarItem>, k?: string) => update(p, k);
  return (
    <Section title="Colour bar" open>
      {!ramp && <p className="muted small">Switch on a continuous satellite layer (rainfall, NDVI…) to fill this bar.</p>}
      <Row label="Label"><input className="input" value={it.label} onChange={(e) => set({ label: e.target.value }, "label")} placeholder={ramp?.label} /></Row>
      <Seg label="Direction" value={it.orientation} options={[["horizontal", "Horizontal"], ["vertical", "Vertical"]]} onChange={(orientation) => set({ orientation })} />
      <div className="ple-grid2">
        <Num label="Values" value={it.ticks} min={2} max={9} onChange={(ticks) => set({ ticks })} />
        <Num label="Text (pt)" value={it.font.size} min={4} step={0.5} onChange={(size) => set({ font: { ...it.font, size } }, "fs")} />
      </div>
    </Section>
  );
}

function PictureProps({ it, update, onError }: { it: PictureItem; update: PropsArgs["update"]; onError: (m: string) => void }) {
  function onFile(file?: File) {
    if (!file) return;
    if (file.size > MAX_PICTURE_BYTES) { onError("Use a picture under 1.5 MB."); return; }
    toDataUrl(file).then((src) => update({ src } as Partial<PictureItem>)).catch(() => onError("That picture couldn't be read."));
  }
  return (
    <Section title="Picture" open>
      <div className="ple-btnrow">
        <button type="button" className={`btn btn-sm ${it.src === ISDB_LOGO ? "btn-dark" : "btn-outline"}`} onClick={() => update({ src: ISDB_LOGO } as Partial<PictureItem>)}>IsDB logo</button>
        <label className="btn btn-outline btn-sm"><Upload aria-hidden="true" />Upload logo or image
          <input type="file" accept="image/png,image/jpeg,image/svg+xml,image/webp" hidden onChange={(e) => onFile(e.target.files?.[0])} />
        </label>
      </div>
      {it.src !== ISDB_LOGO && <img className="ple-pic" src={it.src} alt="" />}
      <Seg label="Fit" value={it.fit} options={[["contain", "Whole picture"], ["cover", "Fill the box"]]} onChange={(fit) => update({ fit } as Partial<PictureItem>)} />
    </Section>
  );
}

function ShapeProps({ it, update }: { it: ShapeItem; update: PropsArgs["update"] }) {
  const set = (p: Partial<ShapeItem>, k?: string) => update(p, k);
  return (
    <Section title="Shape" open>
      <Seg label="Shape" value={it.shape} options={[["rect", "Rectangle"], ["ellipse", "Ellipse"], ["line", "Line"]]} onChange={(shape) => set({ shape, name: { rect: "Rectangle", ellipse: "Ellipse", line: "Line" }[shape] })} />
      {it.shape !== "line" && (
        <div className="ple-grid2">
          <Color label="Fill" value={it.fill || "#ffffff"} onChange={(fill) => set({ fill, fillOpacity: it.fillOpacity || 1 }, "fill")} />
          <Num label="Fill opacity" value={it.fillOpacity} min={0} max={1} step={0.1} onChange={(fillOpacity) => set({ fillOpacity }, "fo")} />
        </div>
      )}
      <div className="ple-grid2">
        <Color label="Line" value={it.stroke || "#1f2937"} onChange={(stroke) => set({ stroke }, "stroke")} />
        <Num label="Line (mm)" value={it.strokeWidth} min={0} step={0.1} onChange={(strokeWidth) => set({ strokeWidth }, "sw")} />
      </div>
    </Section>
  );
}

/* ------------------------------------------------------------------ shared controls */

function FrameEdit({ frame, onChange, isMap }: { frame: Frame; onChange: (f: Frame) => void; isMap: boolean }) {
  const set = (p: Partial<Frame>) => onChange({ ...frame, ...p });
  return (
    <>
      <Check label="Background" checked={!!frame.bg} onChange={(on) => set({ bg: on ? "#ffffff" : "" })} />
      {frame.bg && (
        <div className="ple-grid2">
          <Color label="Colour" value={frame.bg} onChange={(bg) => set({ bg })} />
          <Num label="Opacity" value={frame.bgOpacity} min={0} max={1} step={0.05} onChange={(bgOpacity) => set({ bgOpacity })} />
        </div>
      )}
      <Check label={isMap ? "Frame line" : "Outline"} checked={!!frame.stroke} onChange={(on) => set({ stroke: on ? "#1f2937" : "" })} />
      {frame.stroke && (
        <div className="ple-grid2">
          <Color label="Colour" value={frame.stroke} onChange={(stroke) => set({ stroke })} />
          <Num label="Width (mm)" value={frame.strokeWidth} min={0.05} step={0.05} onChange={(strokeWidth) => set({ strokeWidth })} />
        </div>
      )}
      {!isMap && (
        <div className="ple-grid2">
          <Num label="Padding (mm)" value={frame.padding} min={0} step={0.5} onChange={(padding) => set({ padding })} />
          <div className="ple-row"><span>&nbsp;</span><Check label="Shadow" checked={frame.shadow} onChange={(shadow) => set({ shadow })} /></div>
        </div>
      )}
    </>
  );
}

function FontEdit({ value, onChange }: { value: Font; onChange: (f: Font) => void }) {
  const set = (p: Partial<Font>) => onChange({ ...value, ...p });
  return (
    <div className="ple-font">
      <select className="input" value={value.family} onChange={(e) => set({ family: e.target.value as Font["family"] })} aria-label="Font">
        <option value="sans">Outfit</option><option value="serif">Georgia (serif)</option><option value="mono">Monospace</option>
      </select>
      <input className="input" type="number" min={4} max={120} step={0.5} value={value.size} aria-label="Size (pt)" title="Size in points" onChange={(e) => set({ size: Math.max(4, Number(e.target.value) || 4) })} />
      <select className="input" value={value.weight} aria-label="Weight" onChange={(e) => set({ weight: Number(e.target.value) as Font["weight"] })}>
        <option value={400}>Regular</option><option value={500}>Medium</option><option value={600}>Semibold</option><option value={700}>Bold</option>
      </select>
      <button type="button" className={`ple-ital${value.italic ? " is-on" : ""}`} aria-pressed={value.italic} title="Italic" onClick={() => set({ italic: !value.italic })}>I</button>
      <input className="ple-color ple-color-sm" type="color" value={value.color} aria-label="Colour" onChange={(e) => set({ color: e.target.value })} />
    </div>
  );
}

function ToolBtn({ label, onClick, disabled, active, children }: { label: string; onClick: () => void; disabled?: boolean; active?: boolean; children: ReactNode }) {
  return <button type="button" className={`ple-tool${active ? " is-on" : ""}`} title={label} aria-label={label} aria-pressed={active} disabled={disabled} onClick={onClick}>{children}</button>;
}
function Section({ title, open, grow, children }: { title: string; open?: boolean; grow?: boolean; children: ReactNode }) {
  return <details className={`ple-sec${grow ? " is-grow" : ""}`} open={open}><summary>{title}</summary><div className="ple-sec-body">{children}</div></details>;
}
function Row({ label, children }: { label: string; children: ReactNode }) {
  return <label className="ple-row"><span>{label}</span>{children}</label>;
}
function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return <label className="ple-check"><input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />{label}</label>;
}
function Seg<T extends string>({ label, value, options, onChange }: { label?: string; value: T; options: [T, string][]; onChange: (v: T) => void }) {
  return (
    <div className="ple-row">
      {label && <span>{label}</span>}
      <div className="ple-seg" role="radiogroup" aria-label={label}>
        {options.map(([v, l]) => <button key={v} type="button" role="radio" aria-checked={value === v} className={value === v ? "is-on" : ""} onClick={() => onChange(v)}>{l}</button>)}
      </div>
    </div>
  );
}
function Num({ label, value, min, max, step = 1, onChange }: { label: string; value: number; min?: number; max?: number; step?: number; onChange: (v: number) => void }) {
  const [draft, setDraft] = useState<string | null>(null);
  const shown = draft ?? String(Math.round(value * 100) / 100);
  return (
    <Row label={label}>
      <input className="input" type="number" value={shown} min={min} max={max} step={step}
        onChange={(e) => {
          setDraft(e.target.value);
          const v = Number(e.target.value);
          if (e.target.value !== "" && Number.isFinite(v)) onChange(Math.min(max ?? Infinity, Math.max(min ?? -Infinity, v)));
        }}
        onBlur={() => setDraft(null)} />
    </Row>
  );
}
function Color({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return <Row label={label}><input className="ple-color" type="color" value={value} onChange={(e) => onChange(e.target.value)} /></Row>;
}

