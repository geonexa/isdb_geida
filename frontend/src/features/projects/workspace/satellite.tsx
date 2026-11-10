import "@/shared/styles/catalog.css";

import { useQueries, useQuery } from "@tanstack/react-query";
import { ChevronDown, Download, Grid3x3, Info, LoaderCircle, Search } from "lucide-react";
import { useState } from "react";

import { api, ApiError } from "@/shared/api/client";
import { useToast } from "@/shared/components/Toasts";
import { paletteStops } from "@/shared/map/palettes";

/** Data layers from the Data Catalog, served cut to the project's area. */
export type SatLegend =
  | { type: "ramp"; palette: string[]; min: string; max: string; unit?: string }
  | { type: "classes"; items: [string, string][] };
export type SatLayer = {
  id: string; name: string; source: string; res: string; period: string;
  /** Years, or months ("2024-06") / dates ("2024-06-27") for monthly and dated layers. */
  years?: (number | string)[]; year?: number | string; period_label?: string;
  legend?: SatLegend; attribution?: string; desc?: string; opacity?: number;
  /** A picture from an outside service (NASA GIBS, Terrascope, Esri): no values, no download. */
  view_only?: boolean;
  /** The service has tiles up to this zoom; the map enlarges them beyond. */
  maxzoom?: number;
  /** Drawn from this zoom in (tiled datasets such as the DEM and WorldCover). */
  minzoom?: number;
  /** Project phases the layer is offered in (preparation, implementation, completion). */
  phases?: string[];
  /** Continuous layers drawn with a named palette: the default palette and value range, which users may change. */
  style?: { cmap: string; range: [number, number] };
  /** "pmtiles" for vector tiles drawn in the browser (no GEIDA tile route, no download). */
  kind?: string;
  pmtiles?: PmtilesDef;
};
export type SatGroup = { group: string; layers: SatLayer[] };
/** Vector tiles read by the browser from a PMTiles archive (e.g. Fields of The World), coloured per source layer. */
export type PmtilesDef = {
  url: string; maxzoom?: number;
  layers: {
    source_layer: string; minzoom?: number; maxzoom?: number;
    /** Colour: a linear ramp or classes by `property` (0 left clear with `hide_zero`), or one colour. */
    property?: string; ramp?: [number, string][]; steps?: [number, string][]; hide_zero?: boolean; color?: string;
    /** Outline colour (or default dark line when true). */
    outline?: string | boolean;
    /** Users can hide features below a minimum value of this property (e.g. the model score). */
    threshold_property?: string;
  }[];
};
export const isVectorTiles = (l: SatLayer) => l.kind === "pmtiles" && !!l.pmtiles;
/** Layers switched on, by id: period, opacity, and palette / value range when changed. */
export type SatState = Record<string, { year?: number | string; opacity: number; cmap?: string; range?: [number, number];
  /** Vector tile layers: hide features scoring below this (0 to 100). */
  threshold?: number }>;

export function useSatelliteLayers(code: string, enabled: boolean) {
  return useQuery({
    queryKey: ["satellite", code],
    queryFn: () => api<{ groups: SatGroup[] }>(`/api/projects/${code}/satellite/`).then((d) => d.groups),
    enabled,
    staleTime: Infinity,
  });
}

/** Tile URLs (GEIDA's project tile route: cloud-optimised GeoTIFFs via TiTiler, cut to the area) for every layer switched on. */
export function useSatelliteTiles(code: string, on: SatState) {
  const ids = Object.keys(on);
  const qs = useQueries({
    queries: ids.map((id) => {
      const st = on[id];
      const q = new URLSearchParams();
      if (st.year != null) q.set("year", String(st.year));
      if (st.cmap) q.set("cmap", st.cmap);
      if (st.range) q.set("range", st.range.join(","));
      return {
        queryKey: ["satellite-tiles", code, id, st.year ?? null, st.cmap ?? null, st.range?.join(",") ?? null],
        queryFn: () => api<{ tiles: string[]; attribution: string; minzoom?: number; maxzoom?: number | null }>(
          `/api/projects/${code}/satellite/${id}/tiles/${q.size ? `?${q}` : ""}`),
        staleTime: Infinity, // stable URLs (they change with the period, the style and the area version)
        retry: false,
      };
    }),
  });
  return ids.map((id, i) => ({ id, ...on[id], query: qs[i] }));
}

/** Numeric value of a catalogue legend label ("2,000+" -> 2000). */
export const legendNumber = (s: string) => Number(s.replace(/[^0-9.-]/g, "")) || 0;

const fmt = (v: number) => v.toLocaleString("en", { maximumFractionDigits: 2 });

/** The legend as drawn now: the catalogue's, with the user's palette and value range applied. */
export function effectiveLegend(l: SatLayer, st?: SatState[string]): SatLegend | undefined {
  if (!l.legend || l.legend.type !== "ramp" || !st || (!st.cmap && !st.range)) return l.legend;
  return {
    ...l.legend,
    palette: (st.cmap && paletteStops(st.cmap)) || l.legend.palette,
    ...(st.range ? { min: fmt(st.range[0]), max: fmt(st.range[1]) } : {}),
  };
}

/** Toggle a layer on (at its default period and opacity) or off. */
export function toggleSat(on: SatState, l: SatLayer): SatState {
  const next = { ...on };
  if (next[l.id]) delete next[l.id];
  else next[l.id] = { year: l.year, opacity: l.opacity ?? 0.85 };
  return next;
}

/**
 * Data layers in the Analyses tab: the Data Catalog's rasters in its sections
 * (Climate and water, Vegetation and land, …), cut to the area of influence. Each
 * layer switches on with its period and a GeoTIFF download; display settings
 * (opacity, palette, range) are in the map's Layers panel.
 */
export function DataLayers({ code, groups, on, setOn, errors, loading, phase }: {
  code: string; groups: SatGroup[]; on: SatState; setOn: (s: SatState) => void;
  errors: Record<string, string>; loading: Set<string>;
  /** Only layers offered in this phase are listed (layers already on stay on the map). */
  phase: string;
}) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const patch = (id: string, p: Partial<SatState[string]>) => setOn({ ...on, [id]: { ...on[id], ...p } });

  async function download(l: SatLayer) {
    setDownloading(l.id);
    try {
      const year = on[l.id]?.year ?? l.year;
      const res = await fetch(`/api/projects/${code}/satellite/${l.id}/download/${year ? `?year=${year}` : ""}`, { credentials: "same-origin" });
      if (!res.ok) throw new ApiError(res.status, await res.json().catch(() => ({})));
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `${code}_${l.id}_${year ?? "static"}.tif`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(`${l.name}: GeoTIFF clipped to the area, ${res.headers.get("X-GEIDA-Scale")} m pixels.`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Download failed.", "error");
    } finally { setDownloading(null); }
  }

  const needle = q.trim().toLowerCase();
  const shown = groups
    .map((g) => ({ ...g, layers: g.layers.filter((l) => (!l.phases || l.phases.includes(phase)) && (!needle || `${l.name} ${l.source}`.toLowerCase().includes(needle))) }))
    .filter((g) => g.layers.length);
  const onCount = Object.keys(on).length;

  return (
    <div className="pw-datalayers">
      <p className="muted small">
        Rainfall, water use, vegetation, land cover and terrain from open data, cut to the area of influence.
        Switch a layer on to add it to the map; change its colours and opacity in the map's Layers panel.
      </p>
      <div className="pw-filter">
        <label className="psearch"><Search aria-hidden="true" /><input type="search" placeholder="Search layers or sources" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search data layers" /></label>
        <span className="muted small">{onCount} on the map</span>
      </div>
      <div className="pw-datalayers-list">
        {shown.map((g) => {
          const active = g.layers.filter((l) => on[l.id]).length;
          return (
            <details key={g.group} className="gp-group" open>
              <summary>
                <span className="gp-group-type"><Grid3x3 aria-hidden="true" /></span>
                <span className="gp-group-name">{g.group}</span>
                <span className="gp-group-n">{active ? `${active} / ` : ""}{g.layers.length}</span>
                <ChevronDown className="gp-chev" aria-hidden="true" />
              </summary>
              <ul>
                {g.layers.map((l) => {
                  const st = on[l.id];
                  return (
                    <li key={l.id} className={`gp-item${st ? " is-on" : ""}${loading.has(l.id) ? " is-loading" : ""}`}>
                      <label className="gp-switch">
                        <input type="checkbox" checked={!!st} onChange={() => setOn(toggleSat(on, l))} />
                        <span className="gp-switch-ui" aria-hidden="true"></span>
                        <span className="visually-hidden">Show {l.name}</span>
                      </label>
                      <div className="gp-item-body">
                        <span className="gp-item-name">{l.name}</span>
                        <span className="gp-item-meta">{l.view_only ? "View only · " : ""}{isVectorTiles(l) ? "Vector · " : ""}{l.source} · {l.res}</span>
                      </div>
                      <button type="button" className="gp-icon-btn gp-info-btn" aria-expanded={info === l.id} aria-label={`About ${l.name}`} onClick={() => setInfo(info === l.id ? null : l.id)}>
                        <Info aria-hidden="true" />
                      </button>
                      {st && (
                        <div className="pw-dl-row">
                          {l.years && l.years.length > 1 && (
                            <select className="input" value={st.year} aria-label={`${l.name} ${(l.period_label ?? "year").toLowerCase()}`}
                              onChange={(e) => patch(l.id, { year: typeof l.years![0] === "number" ? Number(e.target.value) : e.target.value })}>
                              {[...l.years].reverse().map((y) => <option key={y} value={y}>{y}</option>)}
                            </select>
                          )}
                          {loading.has(l.id) && <LoaderCircle className="spin pw-sat-spin" aria-label="Loading map tiles" />}
                          {!l.view_only && !isVectorTiles(l) && (
                            <button type="button" className="btn btn-outline btn-sm" title="Download a GeoTIFF of the values, clipped to the area" disabled={downloading === l.id} onClick={() => download(l)}>
                              {downloading === l.id ? <LoaderCircle className="spin" aria-hidden="true" /> : <Download aria-hidden="true" />}GeoTIFF
                            </button>
                          )}
                        </div>
                      )}
                      {st && errors[l.id] && <p className="pw-sat-error">{errors[l.id]}</p>}
                      {info === l.id && (
                        <div className="gp-info">
                          {l.desc && <p>{l.desc}</p>}
                          <dl>
                            <div><dt>Source</dt><dd>{l.source}</dd></div>
                            <div><dt>Resolution</dt><dd>{l.res}</dd></div>
                            <div><dt>Period</dt><dd>{l.period}</dd></div>
                            <div><dt>Use</dt><dd>{l.view_only || isVectorTiles(l) ? "View and print" : "View, print, download"}</dd></div>
                            {isVectorTiles(l) && <div><dt>Note</dt><dd>Fields are drawn in full, not cut to the area outline.</dd></div>}
                          </dl>
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            </details>
          );
        })}
        {shown.length === 0 && <p className="gp-empty">{needle ? "No layers match your search in this phase." : "No data layers for this phase yet."}</p>}
      </div>
      <p className="muted small pw-dl-next">Statistics over the area (zonal mean, totals per unit) for these layers are planned.</p>
    </div>
  );
}

export function SatLegendView({ legend }: { legend?: SatLegend }) {
  if (!legend) return null;
  if (legend.type === "ramp") {
    return (
      <div className="pw-ramp">
        <i style={{ background: `linear-gradient(90deg, ${legend.palette.join(",")})` }} />
        <span>{legend.min}</span><span>{legend.unit}</span><span>{legend.max}</span>
      </div>
    );
  }
  return <ul className="pw-legend pw-sat-classes">{legend.items.map(([c, n]) => <li key={n}><i style={{ background: c }} />{n}</li>)}</ul>;
}
