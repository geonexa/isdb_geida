import "maplibre-gl/dist/maplibre-gl.css";

import type { Feature, FeatureCollection, Geometry } from "geojson";
import "@/features/projects/maplibre-worker";

import * as maplibregl from "maplibre-gl";
import type { ExpressionSpecification, GeoJSONSource, MapLayerMouseEvent, StyleSpecification } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { useEffect, useRef, useState } from "react";
import type React from "react";

import type { BBox, VectorStyle } from "@/features/projects/types";
import type { PmtilesDef } from "@/features/projects/workspace/satellite";
import { colorExpr, radiusExpr, widthExpr } from "@/features/projects/vectorStyle";
import { featurePopupHtml } from "@/features/projects/featurePopup";
import { BasemapPicker } from "@/shared/components/BasemapPicker";
import { saveBasemapId, savedBasemapId, tileUrls, useBasemaps } from "@/shared/map/basemaps";

// "pmtiles://<archive url>" sources (vector tiles read with HTTP range requests). Registered once,
// globally, so the export's offscreen map can read the same sources from getStyle().
maplibregl.addProtocol("pmtiles", new Protocol().tile);

const EMPTY: FeatureCollection = { type: "FeatureCollection", features: [] };
const TEAL = "#0B3B47";
const GOLD = "#C9A25B";
const GREEN = "#2F8F4E";

/** Start with a plain background; the basemap (same list as the Geo-Portal) is added once it loads. */
const INITIAL_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [{ id: "background", type: "background", paint: { "background-color": "#E9ECEE" } }],
};

const fc = (g?: Geometry | null): FeatureCollection =>
  g ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: g }] } : EMPTY;

export type MapProps = {
  className?: string;
  /** Fit to this box whenever it changes. */
  fitBbox?: BBox | null;
  /** Saved area of influence (teal). */
  area?: Geometry | null;
  /** Area being checked, not yet saved (gold, dashed). */
  preview?: Geometry | null;
  /** Project points for the list map; click returns the code. */
  points?: FeatureCollection | null;
  onPointClick?: (code: string) => void;
  /** Admin units to pick from; selected gids are highlighted. */
  units?: FeatureCollection | null;
  selectedUnits?: string[];
  onUnitClick?: (gid: string) => void;
  /** Polygon being drawn, as [lon, lat] vertices. */
  drawCoords?: [number, number][];
  /** Buffer centre. */
  marker?: [number, number] | null;
  onMapClick?: (lngLat: [number, number]) => void;
  cursor?: "crosshair" | "pointer" | "";
  /** Raster previews (PNG) drawn under the area outline, e.g. analysis results. */
  images?: { id: string; url: string; bounds: [number, number, number, number]; opacity?: number }[];
  /** Raster tile layers (satellite data), drawn under analysis results and the area outline. */
  rasters?: { id: string; tiles: string[]; opacity?: number; attribution?: string; minzoom?: number; maxzoom?: number }[];
  /** Vector tile layers read from PMTiles archives (e.g. field boundaries), drawn with the rasters. */
  vectorTiles?: { id: string; url: string; def: PmtilesDef; opacity?: number; threshold?: number; attribution?: string }[];
  /** Ids of raster layers whose map tiles are still loading (called whenever that set changes). */
  onRastersLoading?: (ids: Set<string>) => void;
  /** Vector layers (points, lines, polygons) loaded from a GeoJSON URL, styled by the module. */
  vectors?: { id: string; url: string; style: VectorStyle & { outline?: string; lineOpacity?: number }; title?: string }[];
  /** Display settings chosen in the Layers panel. */
  areaStyle?: { color: string; fillOpacity: number };
  basemapVisible?: boolean;
  background?: string;
  /** Overlay UI drawn on top of the map (layer list, legends, drawers). */
  children?: React.ReactNode;
  /** The MapLibre map once its layers are in place (null on unmount), e.g. for map export. */
  onMap?: (map: maplibregl.Map | null) => void;
  /** Adds an "Export map" button below the fullscreen button. */
  onExport?: () => void;
};

/** MapLibre map for project onboarding: area display, drawing, admin-unit picking. */
export function ProjectMap(props: MapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<maplibregl.Map | null>(null);
  const [ready, setReady] = useState(false);
  const basemaps = useBasemaps().data;
  const [basemap, setBasemap] = useState(() => savedBasemapId() ?? "light");
  const handlers = useRef(props);
  handlers.current = props;
  const popup = useRef<maplibregl.Popup | null>(null);
  /** Paint last applied per vector layer (JSON of its style). */
  const painted = useRef(new Map<string, string>());

  useEffect(() => {
    if (!el.current) return;
    const m = new maplibregl.Map({
      container: el.current,
      style: INITIAL_STYLE,
      center: [30, 15],
      zoom: 2.2,
      attributionControl: { compact: true },
      dragRotate: false,
    });
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    m.addControl(new maplibregl.FullscreenControl(), "top-right");
    if (handlers.current.onExport) m.addControl(new ExportControl(() => handlers.current.onExport?.()), "top-right");
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");
    m.doubleClickZoom.disable();
    m.on("load", () => {
      addLayers(m); setReady(true); handlers.current.onMap?.(m);
      if (import.meta.env.DEV) (window as unknown as { geidaProjectMap?: maplibregl.Map }).geidaProjectMap = m; // for debugging in the console
    });
    m.on("click", (e: MapLayerMouseEvent) => {
      const h = handlers.current;
      if (h.onUnitClick && m.getLayer("units-fill")) {
        const f = m.queryRenderedFeatures(e.point, { layers: ["units-fill"] })[0];
        if (f) { h.onUnitClick(String(f.properties?.gid)); return; }
      }
      if (h.onPointClick && m.getLayer("points")) {
        const f = m.queryRenderedFeatures(e.point, { layers: ["points"] })[0];
        if (f) { h.onPointClick(String(f.properties?.code)); return; }
      }
      // Analysis layers: show the clicked feature's attributes (OSM tags and computed values).
      const vecLayers = (m.getStyle().layers ?? []).map((l) => l.id).filter((id) => id.startsWith("vec-"));
      const hit = vecLayers.length && !h.onMapClick ? m.queryRenderedFeatures(e.point, { layers: vecLayers })[0] : undefined;
      if (hit) {
        const src = String(hit.source);
        const title = h.vectors?.find((v) => `vec-${v.id}` === src)?.title ?? "";
        popup.current?.remove();
        popup.current = new maplibregl.Popup({ className: "pmap-popup", maxWidth: "320px", closeButton: true, focusAfterOpen: false })
          .setLngLat(e.lngLat).setHTML(featurePopupHtml(hit.properties ?? {}, title)).addTo(m);
        return;
      }
      popup.current?.remove();
      h.onMapClick?.([e.lngLat.lng, e.lngLat.lat]);
    });
    for (const layer of ["units-fill", "points"]) {
      m.on("mouseenter", layer, () => { m.getCanvas().style.cursor = "pointer"; });
      m.on("mouseleave", layer, () => { m.getCanvas().style.cursor = handlers.current.cursor ?? ""; });
    }
    map.current = m;
    return () => { handlers.current.onMap?.(null); m.remove(); map.current = null; setReady(false); };
  }, []);

  // Basemap switch: replace the raster under every overlay layer.
  const current = basemaps?.find((b) => b.id === basemap) ?? basemaps?.[0];
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !current) return;
    if (m.getSource("base")) {
      m.removeLayer("base");
      m.removeSource("base");
    }
    m.addSource("base", { type: "raster", tiles: tileUrls(current), tileSize: 256, maxzoom: current.maxZoom ?? 19, attribution: current.attribution });
    const first = m.getStyle().layers?.find((l: { id: string }) => l.id !== "background" && l.id !== "base")?.id;
    m.addLayer({ id: "base", type: "raster", source: "base", layout: { visibility: handlers.current.basemapVisible === false ? "none" : "visible" } }, first);
  }, [current?.id, ready]);

  // Basemap on/off, background colour, area colours.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    if (m.getLayer("base")) m.setLayoutProperty("base", "visibility", props.basemapVisible === false ? "none" : "visible");
    m.setPaintProperty("background", "background-color", props.background ?? "#E9ECEE");
  }, [props.basemapVisible, props.background, ready]);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !props.areaStyle) return;
    m.setPaintProperty("area-fill", "fill-color", props.areaStyle.color);
    m.setPaintProperty("area-fill", "fill-opacity", props.areaStyle.fillOpacity);
    m.setPaintProperty("area-line", "line-color", props.areaStyle.color);
  }, [props.areaStyle?.color, props.areaStyle?.fillOpacity, ready]);

  const set = (id: string, data: FeatureCollection) => {
    const m = map.current;
    if (!m || !ready) return;
    (m.getSource(id) as GeoJSONSource | undefined)?.setData(data);
  };

  useEffect(() => set("area", fc(props.area)), [props.area, ready]);
  useEffect(() => set("preview", fc(props.preview)), [props.preview, ready]);
  useEffect(() => set("points", props.points ?? EMPTY), [props.points, ready]);
  useEffect(() => {
    const sel = new Set(props.selectedUnits ?? []);
    const data = props.units ?? EMPTY;
    set("units", {
      type: "FeatureCollection",
      features: data.features.map((f: Feature) => ({ ...f, properties: { ...f.properties, selected: sel.has(String(f.properties?.gid)) } })),
    });
  }, [props.units, props.selectedUnits, ready]);
  useEffect(() => {
    const c = props.drawCoords ?? [];
    const features: Feature[] = c.map((p) => ({ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: p } }));
    if (c.length >= 2) {
      features.push({ type: "Feature", properties: {}, geometry: { type: "LineString", coordinates: c.length >= 3 ? [...c, c[0]] : c } });
    }
    if (c.length >= 3) {
      features.push({ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [[...c, c[0]]] } });
    }
    set("draw", { type: "FeatureCollection", features });
  }, [props.drawCoords, ready]);
  useEffect(() => {
    set("marker", props.marker ? { type: "FeatureCollection", features: [{ type: "Feature", properties: {}, geometry: { type: "Point", coordinates: props.marker } }] } : EMPTY);
  }, [props.marker, ready]);
  useEffect(() => {
    const m = map.current;
    if (m) m.getCanvas().style.cursor = props.cursor ?? "";
  }, [props.cursor, ready]);

  // Analysis overlays: add/remove image and vector sources as the list changes.
  const imagesKey = (props.images ?? []).map((i) => i.id + i.url).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const want = new Map((props.images ?? []).map((i) => [`img-${i.id}`, i]));
    for (const layer of m.getStyle().layers ?? []) {
      if (layer.id.startsWith("img-") && !want.has(layer.id)) { m.removeLayer(layer.id); m.removeSource(layer.id); }
    }
    for (const [id, i] of want) {
      if (m.getSource(id)) continue;
      const [w, s, e, n] = i.bounds;
      m.addSource(id, { type: "image", url: i.url, coordinates: [[w, n], [e, n], [e, s], [w, s]] });
      m.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": i.opacity ?? 0.85, "raster-resampling": "nearest" } }, "area-fill");
    }
  }, [imagesKey, ready]);
  const imgOpacityKey = (props.images ?? []).map((i) => `${i.id}:${i.opacity}`).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const i of props.images ?? []) if (m.getLayer(`img-${i.id}`)) m.setPaintProperty(`img-${i.id}`, "raster-opacity", i.opacity ?? 0.85);
  }, [imgOpacityKey, imagesKey, ready]);
  const rastersKey = (props.rasters ?? []).map((r) => r.id + r.tiles[0]).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const want = new Map((props.rasters ?? []).map((r) => [`sat-${r.id}`, r]));
    for (const layer of m.getStyle().layers ?? []) {
      const src = m.getSource(layer.id) as { tiles?: string[] } | undefined;
      if (layer.id.startsWith("sat-") && (!want.has(layer.id) || src?.tiles?.[0] !== want.get(layer.id)!.tiles[0])) { m.removeLayer(layer.id); m.removeSource(layer.id); }
    }
    // Keep the panel order: each new layer goes under the analysis images and the area.
    const above = () => m.getStyle().layers?.find((l: { id: string }) => l.id.startsWith("img-"))?.id ?? "units-fill";
    for (const [id, r] of want) {
      if (m.getSource(id)) continue;
      m.addSource(id, { type: "raster", tiles: r.tiles, tileSize: 256, attribution: r.attribution, ...(r.minzoom ? { minzoom: r.minzoom } : {}), ...(r.maxzoom ? { maxzoom: r.maxzoom } : {}) });
      m.addLayer({ id, type: "raster", source: id, paint: { "raster-opacity": r.opacity ?? 0.85 } }, above());
    }
  }, [rastersKey, ready]);
  const vtKey = (props.vectorTiles ?? []).map((v) => v.id + v.url).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const want = new Map((props.vectorTiles ?? []).map((v) => [`vt-${v.id}`, v]));
    const style = m.getStyle();
    for (const [sid, src] of Object.entries(style.sources ?? {})) {
      if (!sid.startsWith("vt-") || (want.has(sid) && (src as { url?: string }).url === `pmtiles://${want.get(sid)!.url}`)) continue;
      for (const l of style.layers ?? []) if ("source" in l && l.source === sid) m.removeLayer(l.id);
      m.removeSource(sid);
    }
    const above = () => m.getStyle().layers?.find((l: { id: string }) => l.id.startsWith("img-"))?.id ?? "units-fill";
    for (const [sid, v] of want) {
      if (m.getSource(sid)) continue;
      m.addSource(sid, { type: "vector", url: `pmtiles://${v.url}`, attribution: v.attribution });
      v.def.layers.forEach((l, i) => {
        const zoom = { ...(l.minzoom ? { minzoom: l.minzoom } : {}), ...(l.maxzoom ? { maxzoom: l.maxzoom } : {}) };
        const filter = vtFilter(l, v.threshold);
        m.addLayer({ id: `${sid}-${i}`, type: "fill", source: sid, "source-layer": l.source_layer, ...zoom, ...(filter ? { filter } : {}),
          paint: { "fill-color": vtColor(l), "fill-opacity": (v.opacity ?? 0.85) * vtFill(l) } }, above());
        if (l.outline) {
          m.addLayer({ id: `${sid}-${i}-line`, type: "line", source: sid, "source-layer": l.source_layer, ...zoom, ...(filter ? { filter } : {}),
            paint: { "line-color": typeof l.outline === "string" ? l.outline : "#1e1e1e", "line-width": 0.8, "line-opacity": v.opacity ?? 0.85 } }, above());
        }
      });
    }
  }, [vtKey, ready]);
  const vtStyleKey = (props.vectorTiles ?? []).map((v) => `${v.id}:${v.opacity}:${v.threshold}`).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const v of props.vectorTiles ?? []) {
      v.def.layers.forEach((l, i) => {
        const id = `vt-${v.id}-${i}`;
        if (!m.getLayer(id)) return;
        m.setPaintProperty(id, "fill-opacity", (v.opacity ?? 0.85) * vtFill(l));
        m.setFilter(id, vtFilter(l, v.threshold) ?? null);
        if (!m.getLayer(`${id}-line`)) return;
        m.setPaintProperty(`${id}-line`, "line-opacity", v.opacity ?? 0.85);
        m.setFilter(`${id}-line`, vtFilter(l, v.threshold) ?? null);
      });
    }
  }, [vtStyleKey, vtKey, ready]);
  // Report which raster layers are still drawing tiles, for the loaders in the side panel and catalog.
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    let last = "";
    const report = () => {
      const ids = new Set<string>();
      for (const id of Object.keys(m.getStyle().sources ?? {})) {
        if (id.startsWith("sat-") && !m.isSourceLoaded(id)) ids.add(id.slice(4));
        if (id.startsWith("vt-") && !m.isSourceLoaded(id)) ids.add(id.slice(3));
      }
      const key = [...ids].sort().join("|");
      if (key !== last) { last = key; handlers.current.onRastersLoading?.(ids); }
    };
    m.on("sourcedataloading", report);
    m.on("sourcedata", report);
    m.on("idle", report);
    return () => { m.off("sourcedataloading", report); m.off("sourcedata", report); m.off("idle", report); };
  }, [ready]);
  const opacityKey = (props.rasters ?? []).map((r) => `${r.id}:${r.opacity}`).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const r of props.rasters ?? []) if (m.getLayer(`sat-${r.id}`)) m.setPaintProperty(`sat-${r.id}`, "raster-opacity", r.opacity ?? 0.85);
  }, [opacityKey, rastersKey, ready]);
  const vectorsKey = (props.vectors ?? []).map((v) => v.id + v.url).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    const want = new Map((props.vectors ?? []).map((v) => [`vec-${v.id}`, v]));
    const style = m.getStyle();
    for (const src of Object.keys(style.sources ?? {})) {
      if (!src.startsWith("vec-") || want.has(src)) continue;
      for (const layer of style.layers ?? []) if ("source" in layer && layer.source === src) m.removeLayer(layer.id);
      m.removeSource(src);
    }
    for (const [id, v] of want) {
      if (m.getSource(id)) continue;
      const s = v.style;
      const color = colorExpr(s) as never;
      m.addSource(id, { type: "geojson", data: v.url });
      m.addLayer({ id: `${id}-fill`, type: "fill", source: id, filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
        paint: { "fill-color": color, "fill-opacity": s.opacity ?? 0.6, "fill-outline-color": s.outline ?? "rgba(255,255,255,0.35)" } });
      m.addLayer({ id: `${id}-line`, type: "line", source: id, filter: ["in", ["geometry-type"], ["literal", ["LineString", "MultiLineString"]]],
        layout: { "line-cap": "round", "line-join": "round" }, paint: { "line-color": color, "line-width": widthExpr(s) as never, "line-opacity": s.lineOpacity ?? 1 } });
      m.addLayer({ id, type: "circle", source: id, filter: ["in", ["geometry-type"], ["literal", ["Point", "MultiPoint"]]],
        paint: { "circle-radius": radiusExpr(s) as never, "circle-color": color, "circle-opacity": s.lineOpacity ?? 1, "circle-stroke-color": s.outline ?? "#fff", "circle-stroke-width": (s.radius ?? 4.5) < 3 ? 0.5 : 1.5 } });
      painted.current.set(id, JSON.stringify(s));
      for (const layer of [`${id}-fill`, `${id}-line`, id]) {
        m.on("mouseenter", layer, () => { if (!handlers.current.onMapClick) m.getCanvas().style.cursor = "pointer"; });
        m.on("mouseleave", layer, () => { m.getCanvas().style.cursor = handlers.current.cursor ?? ""; });
      }
    }
    if (popup.current && !want.size) { popup.current.remove(); popup.current = null; }
    for (const id of [...painted.current.keys()]) if (!want.has(id)) painted.current.delete(id);
  }, [vectorsKey, ready]);
  // Restyle vector layers in place when their display settings change.
  const vecStyleKey = (props.vectors ?? []).map((v) => `${v.id}:${JSON.stringify(v.style)}`).join("|");
  useEffect(() => {
    const m = map.current;
    if (!m || !ready) return;
    for (const v of props.vectors ?? []) {
      const id = `vec-${v.id}`, s = v.style, json = JSON.stringify(s);
      if (!m.getLayer(id) || painted.current.get(id) === json) continue;
      const color = colorExpr(s) as never;
      m.setPaintProperty(`${id}-fill`, "fill-color", color);
      m.setPaintProperty(`${id}-fill`, "fill-opacity", s.opacity ?? 0.6);
      m.setPaintProperty(`${id}-fill`, "fill-outline-color", s.outline ?? "rgba(255,255,255,0.35)");
      m.setPaintProperty(`${id}-line`, "line-color", color);
      m.setPaintProperty(`${id}-line`, "line-width", widthExpr(s) as never);
      m.setPaintProperty(`${id}-line`, "line-opacity", s.lineOpacity ?? 1);
      m.setPaintProperty(id, "circle-color", color);
      m.setPaintProperty(id, "circle-radius", radiusExpr(s) as never);
      m.setPaintProperty(id, "circle-opacity", s.lineOpacity ?? 1);
      m.setPaintProperty(id, "circle-stroke-color", s.outline ?? "#fff");
      painted.current.set(id, json);
    }
  }, [vecStyleKey, ready]);

  // Fit to the box. Until the user pans or zooms, refit whenever the container resizes: the first
  // fit can run before the page layout has settled (0-size or changing container).
  const fitKey = props.fitBbox ? props.fitBbox.map((n) => n.toFixed(4)).join(",") : "";
  const fitted = useRef(false);
  const userMoved = useRef(false);
  useEffect(() => {
    const m = map.current;
    if (!m || !ready || !props.fitBbox) return;
    const fit = (animate: boolean) => {
      const [x0, y0, x1, y1] = handlers.current.fitBbox ?? props.fitBbox!;
      const { width, height } = m.getContainer().getBoundingClientRect();
      if (width < 50 || height < 50) return;
      m.fitBounds([[x0, y0], [x1, y1]], { padding: 48, maxZoom: 13, duration: animate ? 600 : 0 });
    };
    userMoved.current = false;
    fit(fitted.current);
    fitted.current = true;
    const onResize = () => { if (!userMoved.current) fit(false); };
    const onMove = (e: { originalEvent?: unknown }) => { if (e.originalEvent) userMoved.current = true; };
    m.on("resize", onResize);
    m.on("movestart", onMove);
    return () => { m.off("resize", onResize); m.off("movestart", onMove); };
  }, [fitKey, ready]);

  return (
    <div className={`pmap ${props.className ?? ""}`}>
      <div ref={el} className="pmap-canvas" />
      {basemaps && current && (
        <BasemapPicker className="pmap-bmp bmp-up" basemaps={basemaps} value={current.id}
          onChange={(id) => { setBasemap(id); saveBasemapId(id); }} />
      )}
      {props.children}
    </div>
  );
}

const PRINTER_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/></svg>';

/** Map button (same look as zoom and fullscreen) that opens the map export composer. */
class ExportControl implements maplibregl.IControl {
  private el?: HTMLDivElement;
  constructor(private onClick: () => void) {}
  onAdd() {
    this.el = document.createElement("div");
    this.el.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const b = document.createElement("button");
    b.type = "button";
    b.className = "pmap-export";
    b.title = "Export or print map";
    b.setAttribute("aria-label", "Export or print map");
    b.innerHTML = PRINTER_ICON;
    b.addEventListener("click", this.onClick);
    this.el.appendChild(b);
    return this.el;
  }
  onRemove() { this.el?.remove(); }
}

type VtLayer = PmtilesDef["layers"][number];
const vtValue = (property: string): ExpressionSpecification => ["to-number", ["get", property], 0];
/** Fill colour of a vector-tile source layer: linear ramp, classes or one colour. */
function vtColor(l: VtLayer): ExpressionSpecification | string {
  if (l.property && l.ramp) return ["interpolate", ["linear"], vtValue(l.property), ...l.ramp.flat()] as unknown as ExpressionSpecification;
  if (l.property && l.steps) return ["step", vtValue(l.property), l.steps[0][1], ...l.steps.slice(1).flat()] as unknown as ExpressionSpecification;
  return l.color ?? "#0B3B47";
}
/** Outlined layers (field polygons) get a light fill; filled cells a stronger one. */
const vtFill = (l: VtLayer) => (l.outline ? 0.35 : 0.75);
/** Leave zero values clear (`hide_zero`) and hide features below the user's minimum (none when 0 or unset). */
function vtFilter(l: VtLayer, threshold?: number): ExpressionSpecification | undefined {
  const parts: ExpressionSpecification[] = [];
  if (l.hide_zero && l.property) parts.push([">", vtValue(l.property), 0]);
  if (threshold && l.threshold_property) parts.push([">=", vtValue(l.threshold_property), threshold]);
  return parts.length > 1 ? ["all", ...parts] as ExpressionSpecification : parts[0];
}

function addLayers(m: maplibregl.Map) {
  for (const id of ["units", "area", "preview", "draw", "marker", "points"]) {
    m.addSource(id, { type: "geojson", data: EMPTY });
  }
  m.addLayer({ id: "units-fill", type: "fill", source: "units", paint: {
    "fill-color": ["case", ["get", "selected"], GOLD, "#ffffff"],
    "fill-opacity": ["case", ["get", "selected"], 0.45, 0.05],
  } });
  m.addLayer({ id: "units-line", type: "line", source: "units", paint: { "line-color": TEAL, "line-width": 0.8, "line-opacity": 0.7 } });
  m.addLayer({ id: "area-fill", type: "fill", source: "area", paint: { "fill-color": TEAL, "fill-opacity": 0.18 } });
  m.addLayer({ id: "area-line", type: "line", source: "area", paint: { "line-color": TEAL, "line-width": 2.5 } });
  m.addLayer({ id: "preview-fill", type: "fill", source: "preview", paint: { "fill-color": GOLD, "fill-opacity": 0.25 } });
  m.addLayer({ id: "preview-line", type: "line", source: "preview", paint: { "line-color": GOLD, "line-width": 2.5, "line-dasharray": [2, 1.5] } });
  m.addLayer({ id: "draw-fill", type: "fill", source: "draw", filter: ["==", ["geometry-type"], "Polygon"], paint: { "fill-color": GOLD, "fill-opacity": 0.2 } });
  m.addLayer({ id: "draw-line", type: "line", source: "draw", filter: ["==", ["geometry-type"], "LineString"], paint: { "line-color": GOLD, "line-width": 2 } });
  m.addLayer({ id: "draw-pts", type: "circle", source: "draw", filter: ["==", ["geometry-type"], "Point"], paint: { "circle-radius": 5, "circle-color": "#fff", "circle-stroke-color": TEAL, "circle-stroke-width": 2 } });
  m.addLayer({ id: "marker", type: "circle", source: "marker", paint: { "circle-radius": 7, "circle-color": GOLD, "circle-stroke-color": TEAL, "circle-stroke-width": 2 } });
  m.addLayer({ id: "points", type: "circle", source: "points", paint: {
    "circle-radius": 7,
    "circle-color": ["match", ["get", "status"], "published", GREEN, "review", GOLD, "#8A8A90"],
    "circle-stroke-color": "#fff",
    "circle-stroke-width": 2,
  } });
}
