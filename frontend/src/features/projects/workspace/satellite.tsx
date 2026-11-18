import "@/shared/styles/catalog.css";

import { useQueries, useQuery } from "@tanstack/react-query";
import { Download, Film, Info, LoaderCircle, Pause, Play, Repeat, SkipBack, SkipForward } from "lucide-react";
import { useEffect, useState } from "react";

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
  /** The Analyses category the layer is listed in (water, land, hazards, …), and the planned analysis it belongs to. */
  category?: string; analysis?: string;
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
  threshold?: number;
  /** Periods the map loads in the background (the next frames of a playing time series). */
  preload?: (number | string)[];
  /** The time series player is open: the map shows the layer's date. */
  series?: boolean }>;

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
 * Data Catalog layers that no analysis uses yet, listed in their Analyses category: each switches on
 * with its period and (for value layers) a GeoTIFF download, cut to the area of influence. Display
 * settings (opacity, palette, range) are in the map's Layers panel.
 */
export function LayerList({ code, layers, on, setOn, errors, loading }: {
  code: string; layers: SatLayer[]; on: SatState; setOn: (s: SatState) => void;
  errors: Record<string, string>; loading: Set<string>;
}) {
  const toast = useToast();
  const [info, setInfo] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const [series, setSeries] = useState<string | null>(null);
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

  return (
    <ul className="pw-layer-list">
      {layers.map((l) => {
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
                {l.years && l.years.length > 2 && (
                  <button type="button" className={`btn btn-outline btn-sm${series === l.id ? " is-on" : ""}`} aria-expanded={series === l.id}
                    title="Play the layer through a range of dates" onClick={() => {
                      const open = series !== l.id;
                      const next = { ...on };
                      if (series && next[series]) next[series] = { ...next[series], series: false, preload: [] };
                      next[l.id] = { ...next[l.id], series: open, ...(open ? {} : { preload: [] }) };
                      setOn(next);
                      setSeries(open ? l.id : null);
                    }}>
                    <Film aria-hidden="true" />Time series
                  </button>
                )}
                {loading.has(l.id) && <LoaderCircle className="spin pw-sat-spin" aria-label="Loading map tiles" />}
                {!l.view_only && !isVectorTiles(l) && (
                  <button type="button" className="btn btn-outline btn-sm" title="Download a GeoTIFF of the values, clipped to the area" disabled={downloading === l.id} onClick={() => download(l)}>
                    {downloading === l.id ? <LoaderCircle className="spin" aria-hidden="true" /> : <Download aria-hidden="true" />}GeoTIFF
                  </button>
                )}
              </div>
            )}
            {st && series === l.id && l.years && (
              <TimeSeries layer={l} value={st.year} loading={loading.has(l.id)}
                onChange={(y) => patch(l.id, { year: y })}
                onPreload={(ys) => { if ((st.preload ?? []).join() !== ys.join()) patch(l.id, { preload: ys }); }} />
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
    </ul>  );
}

const SPEEDS = [{ ms: 500, label: "0.5 s" }, { ms: 1000, label: "1 s" }, { ms: 2000, label: "2 s" }, { ms: 3000, label: "3 s" }];

/**
 * Time series player for a layer with several dates (Wayback imagery, monthly NDVI, yearly WaPOR): choose
 * the first and last date, then drag the slider or play. A frame stays on screen for the chosen time once
 * its tiles have loaded, so slow imagery never skips.
 */
export function TimeSeries({ layer, value, loading, onChange, onPreload }: {
  layer: SatLayer; value?: number | string; loading: boolean; onChange: (y: number | string) => void;
  /** The next frames to load in the background while playing (empty when paused). */
  onPreload?: (ys: (number | string)[]) => void;
}) {
  const dates = layer.years ?? [];
  const last = dates.length - 1;
  const at = Math.max(0, dates.findIndex((d) => String(d) === String(value)));
  const [from, setFrom] = useState(() => Math.max(0, (at || last) - 9));
  const [to, setTo] = useState(() => at || last);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1000);
  const [loop, setLoop] = useState(true);
  const label = (layer.period_label ?? "Year").toLowerCase();
  const go = (i: number) => onChange(dates[Math.min(Math.max(i, 0), last)]);

  useEffect(() => {
    if (!playing || loading) return;
    const t = window.setTimeout(() => {
      if (at < from || at >= to) {
        if (at >= to && !loop) { setPlaying(false); return; }
        go(from);
      } else go(at + 1);
    }, speed);
    return () => window.clearTimeout(t);
  }, [playing, loading, at, from, to, speed, loop]); // eslint-disable-line react-hooks/exhaustive-deps

  // While playing, the map loads the next two frames in the background so they show without waiting.
  useEffect(() => {
    if (!onPreload) return;
    if (!playing) { onPreload([]); return; }
    const next: (number | string)[] = [];
    for (let k = 1, i = at; k <= 2 && to > from; k++) {
      i = i >= to || i < from ? from : i + 1;
      if (i !== at) next.push(dates[i]);
    }
    onPreload(next);
  }, [playing, at, from, to]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => onPreload?.([]), []); // eslint-disable-line react-hooks/exhaustive-deps

  const frames = to - from + 1;
  const frame = at >= from && at <= to ? at - from + 1 : 0;
  return (
    <div className="pw-ts" role="group" aria-label={`${layer.name} time series`}>
      <div className="pw-ts-range">
        <label>From
          <select className="input" value={from} onChange={(e) => { const v = Number(e.target.value); setFrom(v); if (v > to) setTo(v); }}>
            {dates.map((d, i) => <option key={String(d)} value={i}>{d}</option>)}
          </select>
        </label>
        <label>To
          <select className="input" value={to} onChange={(e) => { const v = Number(e.target.value); setTo(v); if (v < from) setFrom(v); }}>
            {dates.map((d, i) => <option key={String(d)} value={i}>{d}</option>)}
          </select>
        </label>
      </div>
      <input type="range" className="pw-ts-slider" min={from} max={to} step={1} value={Math.min(Math.max(at, from), to)}
        aria-label={`${layer.name} ${label}`} aria-valuetext={String(dates[at] ?? "")}
        onChange={(e) => { setPlaying(false); go(Number(e.target.value)); }} />
      <div className="pw-ts-ticks" aria-hidden="true"><span>{dates[from]}</span><span>{dates[to]}</span></div>
      <div className="pw-ts-controls">
        <button type="button" className="icon-btn" aria-label="Previous date" disabled={at <= from} onClick={() => { setPlaying(false); go(at - 1); }}><SkipBack aria-hidden="true" /></button>
        <button type="button" className="btn btn-dark btn-sm pw-ts-play" onClick={() => { if (!playing && (at < from || at >= to)) go(from); setPlaying(!playing); }}>
          {playing ? <><Pause aria-hidden="true" />Pause</> : <><Play aria-hidden="true" />Play</>}
        </button>
        <button type="button" className="icon-btn" aria-label="Next date" disabled={at >= to} onClick={() => { setPlaying(false); go(at + 1); }}><SkipForward aria-hidden="true" /></button>
        <select className="input pw-ts-speed" value={speed} aria-label="Time per frame" onChange={(e) => setSpeed(Number(e.target.value))}>
          {SPEEDS.map((sp) => <option key={sp.ms} value={sp.ms}>{sp.label} / frame</option>)}
        </select>
        <button type="button" className={`icon-btn${loop ? " is-on" : ""}`} aria-pressed={loop} aria-label="Loop" title="Start again after the last date" onClick={() => setLoop(!loop)}><Repeat aria-hidden="true" /></button>
      </div>
      <p className="pw-ts-now" aria-live="polite">
        <strong>{dates[at]}</strong>
        <span>{frame ? `Frame ${frame} of ${frames}` : `${frames} frames`}{loading ? " · loading…" : ""}</span>
      </p>
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
