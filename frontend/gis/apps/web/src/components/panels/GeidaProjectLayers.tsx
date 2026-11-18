import type { RefObject } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { addRasterToMap } from "@geolibre/plugins";
import { COLORMAP_OPTIONS, COLORMAP_ROW_COUNT, colormapsPngUrl } from "maplibre-gl-raster";
import { useAppStore } from "@geolibre/core";
import type { MapEngine } from "@geolibre/map";
import { ChevronDown, ChevronRight, FolderOpen, Grid3x3, Loader2, Plus, Shapes, Check } from "lucide-react";

import { createAppAPI } from "../../hooks/usePlugins";

/**
 * GEIDA: a project's data layers (area of influence, analysis outputs, Toolbox outputs) listed under the Layers
 * panel, from GET /api/projects/<code>/layers/. "Add" loads one into this map as an ordinary GeoLibre layer
 * (vectors as GeoJSON, rasters as GeoTIFF), so every Analytics tool can use it.
 */

interface ProjectItem {
  code: string;
  title: string;
  country_name?: string;
  area?: unknown;
}

interface ProjectLayer {
  id: string;
  group: "Project" | "Analyses" | "Toolbox";
  title: string;
  source: string;
  kind: "vector" | "raster";
  format: "geojson" | "geotiff";
  url: string;
  created?: string;
  size_bytes?: number | null;
  style?: { color?: string; outline?: string; opacity?: number; width?: number };
}

const STORE_KEY = "geida.analytics.project";
const SIGNED_OUT = "Sign in to add your projects\u2019 layers.";
const GROUPS: ProjectLayer["group"][] = ["Project", "Analyses", "Toolbox"];
const GROUP_LABEL: Record<ProjectLayer["group"], string> = {
  Project: "Project",
  Analyses: "Analysis results",
  Toolbox: "Toolbox results",
};

function remembered(): string {
  try {
    const fromUrl = new URLSearchParams(window.location.search).get("project");
    return (fromUrl || localStorage.getItem(STORE_KEY) || "").toUpperCase();
  } catch {
    return "";
  }
}

function remember(code: string) {
  try {
    if (code) localStorage.setItem(STORE_KEY, code);
    else localStorage.removeItem(STORE_KEY);
  } catch {
    /* storage unavailable: the choice just isn't kept */
  }
}

async function getJson<T>(url: string): Promise<T> {
  const r = await fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } });
  if (r.status === 401) throw new Error(SIGNED_OUT);
  if (!r.ok) {
    let msg = `Request failed (${r.status}).`;
    try {
      msg = ((await r.json()) as { error?: string }).error || msg;
    } catch {
      /* not JSON */
    }
    throw new Error(msg);
  }
  return (await r.json()) as T;
}

function size(bytes?: number | null) {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
}

function bbox(fc: GeoJSON.FeatureCollection): [number, number, number, number] | null {
  let w = Infinity, s = Infinity, e = -Infinity, n = -Infinity;
  const walk = (c: unknown): void => {
    if (!Array.isArray(c)) return;
    if (typeof c[0] === "number" && typeof c[1] === "number") {
      w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
      return;
    }
    c.forEach(walk);
  };
  for (const f of fc.features) {
    const g = f.geometry as { coordinates?: unknown; geometries?: { coordinates?: unknown }[] } | null;
    if (!g) continue;
    if (g.geometries) g.geometries.forEach((x) => walk(x.coordinates));
    else walk(g.coordinates);
  }
  return Number.isFinite(w) ? [w, s, e, n] : null;
}


// Raster colours ----------------------------------------------------------------------------------------------
// GEIDA's legends use their own palettes; the raster renderer draws named colour maps only (or a GeoTIFF's colour
// table). Continuous rasters take the named map closest to the legend, read from the renderer's own sprite.
interface RasterStyle {
  colormap?: string;
  nodata?: number;
  palette?: string[];
  min?: number;
  max?: number;
  unit?: string;
}

const SAMPLES = 9;
// Qualitative and cyclic maps never stand in for a ramp.
const NOT_RAMPS = new Set(["accent", "dark2", "paired", "pastel1", "pastel2", "set1", "set2", "set3", "tab10", "tab20",
  "tab20b", "tab20c", "flag", "prism", "hsv", "phase", "twilight", "twilight_shifted", "gist_ncar", "gist_rainbow",
  "gist_stern", "nipy_spectral", "brg", "cmrmap", "cubehelix", "rplumbo", "schwarzwald", "cfastie"]);
let spriteRows: Promise<Map<string, number[][]>> | null = null;

function sprite(): Promise<Map<string, number[][]>> {
  spriteRows ??= new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const c = document.createElement("canvas");
      c.width = img.width;
      c.height = img.height;
      const g = c.getContext("2d", { willReadFrequently: true });
      if (!g) return reject(new Error("no canvas"));
      g.drawImage(img, 0, 0);
      const rowH = img.height / COLORMAP_ROW_COUNT;
      const rows = new Map<string, number[][]>();
      for (const o of COLORMAP_OPTIONS) {
        if (o.reversed || NOT_RAMPS.has(o.name)) continue;
        const y = Math.floor(o.rowIndex * rowH + rowH / 2);
        const px: number[][] = [];
        for (let i = 0; i < SAMPLES; i++) {
          const x = Math.min(img.width - 1, Math.round((i / (SAMPLES - 1)) * (img.width - 1)));
          const d = g.getImageData(x, y, 1, 1).data;
          px.push([d[0], d[1], d[2]]);
        }
        rows.set(o.name, px);
      }
      resolve(rows);
    };
    img.onerror = () => reject(new Error("colour maps unavailable"));
    img.src = colormapsPngUrl as unknown as string;
  });
  return spriteRows;
}

function rampSamples(palette: string[]): number[][] {
  const stops = palette.map((h) => {
    const x = h.replace("#", "");
    return [0, 2, 4].map((i) => parseInt(x.slice(i, i + 2), 16));
  });
  return Array.from({ length: SAMPLES }, (_, i) => {
    const t = (i / (SAMPLES - 1)) * (stops.length - 1);
    const k = Math.min(Math.floor(t), stops.length - 2);
    const f = t - k;
    return stops[k].map((v, j) => v + (stops[k + 1][j] - v) * f);
  });
}

async function nearestColormap(palette: string[]): Promise<{ colormap: string; reversed: boolean }> {
  const want = rampSamples(palette);
  let best = { colormap: "viridis", reversed: false, d: Infinity };
  for (const [name, px] of await sprite()) {
    for (const reversed of [false, true]) {
      let d = 0;
      for (let i = 0; i < SAMPLES; i++) {
        const a = want[i];
        const b = px[reversed ? SAMPLES - 1 - i : i];
        d += (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2;
      }
      if (d < best.d) best = { colormap: name, reversed, d };
    }
  }
  return { colormap: best.colormap, reversed: best.reversed };
}

async function rasterState(style: RasterStyle | null) {
  if (!style) return {};
  if (style.colormap === "palette") {
    return { mode: "single" as const, bands: [1], colormap: "palette", nodata: style.nodata ?? 255 };
  }
  if (!style.palette || style.palette.length < 2) return {};
  const { colormap, reversed } = await nearestColormap(style.palette).catch(() => ({ colormap: "viridis", reversed: false }));
  return {
    mode: "single" as const,
    bands: [1],
    colormap,
    reversed,
    ...(typeof style.min === "number" && typeof style.max === "number" && style.max > style.min
      ? { rescale: [[style.min, style.max]] as [number, number][] }
      : {}),
  };
}

export function GeidaProjectLayers({ mapControllerRef }: { mapControllerRef: RefObject<MapEngine | null> }) {
  const [open, setOpen] = useState(true);
  const [projects, setProjects] = useState<ProjectItem[] | null>(null);
  const [projectsError, setProjectsError] = useState("");
  const [code, setCode] = useState(remembered);
  const [layers, setLayers] = useState<ProjectLayer[] | null>(null);
  const [layersError, setLayersError] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [failed, setFailed] = useState<Record<string, string>>({});
  // GEIDA layer id -> GeoLibre layer id, for layers added from this list.
  const [added, setAdded] = useState<Record<string, string>>({});
  // Layers being loaded right now; a ref, so a quick second click sees it before React re-renders.
  const loading = useRef(new Set<string>());
  // Map layers as "id\tname\tsourcePath" lines: enough to tell which project layers are already on the map.
  const mapLayers = useAppStore((s) => s.layers.map((l) => `${l.id}\t${l.name}\t${l.sourcePath ?? ""}`).join("\n"));

  useEffect(() => {
    let live = true;
    getJson<{ projects: ProjectItem[] }>("/api/projects/")
      .then((d) => live && setProjects(d.projects))
      .catch((err: Error) => live && setProjectsError(err.message));
    return () => {
      live = false;
    };
  }, []);

  useEffect(() => {
    setLayers(null);
    setLayersError("");
    setFailed({});
    if (!code) return;
    let live = true;
    getJson<{ layers: ProjectLayer[] }>(`/api/projects/${encodeURIComponent(code)}/layers/`)
      .then((d) => live && setLayers(d.layers))
      .catch((err: Error) => live && setLayersError(err.message));
    return () => {
      live = false;
    };
  }, [code]);

  const layerName = (layer: ProjectLayer) =>
    layer.group === "Project" ? `${layer.title} (${code})` : `${layer.title} · ${layer.source}`;

  // The map layer showing a project layer, if any: the one added from this list in this visit, otherwise one with
  // its source tag (vectors) or its name (rasters), e.g. after a reload of a saved Analytics project.
  const mapLayerOf = useMemo(() => {
    const rows = mapLayers ? mapLayers.split("\n").map((r) => r.split("\t")) : [];
    return (layer: ProjectLayer): string | undefined => {
      const mine = added[layer.id];
      if (mine && rows.some((r) => r[0] === mine)) return mine;
      const tag = `geida:${code}/${layer.id}`;
      return (rows.find((r) => r[2] === tag) ?? rows.find((r) => r[1] === layerName(layer)))?.[0];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [added, mapLayers, code]);

  const removeLayer = (layer: ProjectLayer) => {
    const id = mapLayerOf(layer);
    if (id) useAppStore.getState().removeLayer(id);
    setAdded((a) => {
      const next = { ...a };
      delete next[layer.id];
      return next;
    });
  };

  const grouped = useMemo(
    () => GROUPS.map((g) => [g, (layers ?? []).filter((l) => l.group === g)] as const).filter(([, ls]) => ls.length),
    [layers],
  );

  const addLayer = async (layer: ProjectLayer) => {
    if (loading.current.has(layer.id) || mapLayerOf(layer)) return;     // one copy per project layer
    loading.current.add(layer.id);
    setBusy((b) => ({ ...b, [layer.id]: true }));
    setFailed((f) => ({ ...f, [layer.id]: "" }));
    const name = layerName(layer);
    try {
      const r = await fetch(layer.url, { credentials: "same-origin" });
      if (!r.ok) throw new Error(`The file couldn't be read (${r.status}).`);
      let id: string;
      if (layer.kind === "vector") {
        const fc = (await r.json()) as GeoJSON.FeatureCollection;
        const store = useAppStore.getState();
        id = store.addGeoJsonLayer(name, fc, `geida:${code}/${layer.id}`);
        const st = layer.style;
        if (st && (st.color || st.outline)) {
          const current = useAppStore.getState().layers.find((l) => l.id === id);
          if (current) {
            store.updateLayer(id, {
              style: {
                ...current.style,
                ...(st.color ? { fillColor: st.color } : {}),
                strokeColor: st.outline || st.color || current.style.strokeColor,
                ...(typeof st.opacity === "number" ? { fillOpacity: st.opacity } : {}),
                ...(typeof st.width === "number" ? { strokeWidth: st.width } : {}),
              },
            });
          }
        }
        const b = bbox(fc);
        if (b) mapControllerRef.current?.fitBounds(b);
      } else {
        let style: RasterStyle | null = null;
        try {
          style = JSON.parse(r.headers.get("X-GEIDA-Style") || "null") as RasterStyle | null;
        } catch {
          style = null;
        }
        const blob = await r.blob();
        const file = new File([blob], `${layer.id}.tif`, { type: "image/tiff" });
        const state = await rasterState(style);
        id = await addRasterToMap(createAppAPI(mapControllerRef), file, { name, zoomTo: true, state });
      }
      setAdded((a) => ({ ...a, [layer.id]: id }));
    } catch (err) {
      setFailed((f) => ({ ...f, [layer.id]: err instanceof Error ? err.message : "The layer couldn't be added." }));
    } finally {
      loading.current.delete(layer.id);
      setBusy((b) => ({ ...b, [layer.id]: false }));
    }
  };

  const withArea = (projects ?? []).filter((p) => p.area);
  const signedOut = projectsError === SIGNED_OUT;

  return (
    <section className="geida-proj w-0 min-w-full border-b" aria-label="Project layers">
      {/* w-0 min-w-full: long names must not widen the panel's grid column */}
      <button
        type="button"
        className="geida-proj-toggle flex w-full items-center gap-1.5 text-start text-xs font-semibold uppercase tracking-wide hover:text-foreground"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        {open ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
        <FolderOpen className="h-3.5 w-3.5" />
        Project layers
        {layers ? <span className="ms-auto font-normal normal-case">{layers.length}</span> : null}
      </button>
      {open ? (
        <div className="geida-proj-body">
          {projectsError ? (
            <p className="py-1 text-xs text-muted-foreground">
              {projectsError}{" "}
              {signedOut ? (
                <a
                  className="text-primary underline"
                  href={`/accounts/sign-in?next=${encodeURIComponent(window.location.pathname + window.location.search)}`}
                >
                  Sign in
                </a>
              ) : null}
            </p>
          ) : (
            <select
              className="geida-proj-select w-full"
              value={code}
              aria-label="Project"
              disabled={!projects}
              onChange={(e) => {
                setCode(e.target.value);
                remember(e.target.value);
              }}
            >
              <option value="">{projects ? "Choose a project…" : "Loading projects…"}</option>
              {code && projects && !withArea.some((p) => p.code === code) ? <option value={code}>{code}</option> : null}
              {withArea.map((p) => (
                <option key={p.code} value={p.code}>
                  {p.code} · {p.title}
                </option>
              ))}
            </select>
          )}
          {code && !projectsError ? (
            <div className="geida-proj-list mt-1 max-h-[38vh] overflow-y-auto">
              {layersError ? <p className="py-1 text-xs text-destructive">{layersError}</p> : null}
              {!layers && !layersError ? (
                <p className="flex items-center gap-1.5 py-1 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading layers…
                </p>
              ) : null}
              {layers && layers.length <= 1 ? (
                <p className="py-1 text-xs text-muted-foreground">
                  No analysis or Toolbox results yet. Run analyses or tools in the project workspace and their layers
                  appear here.
                </p>
              ) : null}
              {grouped.map(([group, ls]) => (
                <div key={group}>
                  <div className="geida-proj-group">
                    {GROUP_LABEL[group]} <span className="font-normal">({ls.length})</span>
                  </div>
                  <ul>
                    {ls.map((l) => {
                      const isOn = !!mapLayerOf(l);
                      return (
                        <li key={l.id} className="geida-proj-row flex items-center gap-2 hover:bg-muted/60">
                          {l.kind === "raster" ? (
                            <Grid3x3 className="h-3.5 w-3.5 shrink-0 text-muted-foreground" aria-label="Raster" />
                          ) : (
                            <Shapes
                              className="h-3.5 w-3.5 shrink-0"
                              style={{ color: l.style?.color || l.style?.outline || undefined }}
                              aria-label="Vector"
                            />
                          )}
                          <div className="min-w-0 flex-1">
                            <div className="geida-proj-title truncate" title={l.title}>{l.title}</div>
                            <div className="truncate text-[10px] text-muted-foreground" title={l.source}>
                              {l.group === "Project" ? (l.kind === "vector" ? "Vector" : "Raster") : l.source}
                              {l.size_bytes ? ` · ${size(l.size_bytes)}` : ""}
                            </div>
                            {failed[l.id] ? <div className="text-[10px] text-destructive">{failed[l.id]}</div> : null}
                          </div>
                          <button
                            type="button"
                            className={`geida-proj-add inline-flex shrink-0 items-center gap-1 disabled:opacity-60${isOn ? " is-on" : ""}`}
                            disabled={busy[l.id]}
                            title={isOn ? "On the map: click to remove it" : "Add to the map"}
                            aria-label={isOn ? `Remove ${l.title} from the map` : `Add ${l.title} to the map`}
                            onClick={() => (isOn ? removeLayer(l) : void addLayer(l))}
                          >
                            {busy[l.id] ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : isOn ? (
                              <Check className="h-3 w-3" />
                            ) : (
                              <Plus className="h-3 w-3" />
                            )}
                            <span className="geida-proj-add-label">{isOn ? "Added" : "Add"}</span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
