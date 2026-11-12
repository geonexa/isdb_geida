import { ChevronDown, Download, Layers, Maximize2, Minimize2, Palette, RotateCcw, X } from "lucide-react";
import { useState, type ReactNode } from "react";

import { applyVectorOverride, type LayerStyles, type VectorOverride } from "@/features/projects/layerStyle";
import type { Run, RunOutput, VectorStyle } from "@/features/projects/types";
import { legendSwatches } from "@/features/projects/vectorStyle";
import type { TableOut } from "@/features/projects/workspace/RunParts";
import { downloadToolLayer, type ToolLayer } from "@/features/projects/workspace/toolResults";
import { fmtNum } from "@/features/projects/workspace/data";
import { effectiveLegend, isVectorTiles, SatLegendView, toggleSat, type SatLayer, type SatState } from "@/features/projects/workspace/satellite";
import { cssGradient, PALETTES } from "@/shared/map/palettes";

type ImageOut = Extract<RunOutput, { type: "image" | "raster" }>;
type VectorOut = Extract<RunOutput, { type: "vector" }>;

/**
 * Floating layer list on the map: area of influence, data layers and the open
 * run's outputs, each with its legend and display settings (opacity, colours, palette,
 * value range, size). Settings are kept per project in the browser.
 */
export function LayerPanel({ showArea, onToggleArea, run, hidden, onToggle, onClearRun, styles, setStyles, satLayers, sat, setSat, satLoading, tools, onToolPatch, onToolRemove }: {
  showArea: boolean; onToggleArea: () => void;
  run?: Run; hidden: Set<string>; onToggle: (name: string) => void; onClearRun: () => void;
  styles: LayerStyles; setStyles: (s: LayerStyles) => void;
  /** Data layers switched on (in panel order) and their state. */
  satLayers: SatLayer[]; sat: SatState; setSat: (s: SatState) => void; satLoading: Set<string>;
  /** Toolbox results switched on for the map (saved on the server; shown this visit). */
  tools: ToolLayer[]; onToolPatch: (id: string, p: Partial<ToolLayer>) => void; onToolRemove: (id: string) => void;
}) {
  const [open, setOpen] = useState(() => typeof window === "undefined" || window.matchMedia("(min-width: 901px)").matches);
  const [editing, setEditing] = useState<string | null>(null);
  const outs = run?.status === "done" ? run.outputs ?? [] : [];
  const images = outs.filter((o) => o.type === "image" || o.type === "raster") as ImageOut[];
  const vectors = outs.filter((o) => o.type === "vector") as VectorOut[];
  const count = 1 + images.length + vectors.length + satLayers.length + tools.length;
  const edit = (id: string) => setEditing(editing === id ? null : id);
  const vecOv = (name: string, p: Partial<VectorOverride> | null) =>
    setStyles({ ...styles, vectors: { ...styles.vectors, [name]: p ? { ...styles.vectors[name], ...p } : {} } });
  const patchSat = (id: string, p: Partial<SatState[string]>) => setSat({ ...sat, [id]: { ...sat[id], ...p } });

  return (
    <div className={`pw-layers${open ? " is-open" : ""}`}>
      <button type="button" className="pw-layers-head" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <Layers aria-hidden="true" />Layers<span className="muted small">{count}</span><ChevronDown className="pw-chev" aria-hidden="true" />
      </button>
      {open && (
        <div className="pw-layers-body">
          {tools.length > 0 && (
            <div className="pw-layer-group">
              <div className="pw-layer-group-head"><span>Toolbox results</span></div>
              {tools.map((l) => {
                const id = `tool:${l.id}`;
                return (
                  <div key={l.id}>
                    <div className="pw-layer">
                      <input type="checkbox" checked={l.visible} onChange={() => onToolPatch(l.id, { visible: !l.visible })} aria-label={`Show ${l.name}`} />
                      <span className="pw-layer-name" title={`${l.name}\n${l.source}`}>{l.name}</span>
                      <StyleBtn active={editing === id} onClick={() => edit(id)} />
                      <button type="button" className="icon-btn icon-btn-xs" aria-label={`Download ${l.name}`} title={`Download (${l.downloadLabel})`} onClick={() => downloadToolLayer(l)}><Download aria-hidden="true" /></button>
                      <button type="button" className="icon-btn icon-btn-xs" aria-label={`Remove ${l.name}`} title="Remove from map" onClick={() => onToolRemove(l.id)}><X aria-hidden="true" /></button>
                    </div>
                    {editing === id && (
                      <div className="pw-style">
                        <Opacity value={l.opacity} onChange={(opacity) => onToolPatch(l.id, { opacity })} />
                      </div>
                    )}
                    {l.visible && l.legend.length > 0 && (
                      <ul className="pw-tool-legend">{l.legend.slice(0, 12).map((it, i) => (
                        <li key={i}><i style={{ background: it.color }} />{it.label}</li>
                      ))}</ul>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {/* Analysis outputs on top, as on the map */}
          {run && (images.length > 0 || vectors.length > 0) && (
            <div className="pw-layer-group">
              <div className="pw-layer-group-head">
                <span title={run.module_title}>{run.module_title} <span className="muted">#{run.id}</span></span>
                <button type="button" className="icon-btn icon-btn-xs" aria-label="Remove run layers" title="Remove run layers" onClick={onClearRun}><X aria-hidden="true" /></button>
              </div>
              {vectors.map((o) => {
                const st = applyVectorOverride(o.style, styles.vectors[o.name]);
                const sw = legendSwatches(st);
                const id = `vec:${o.name}`;
                return (
                  <div key={o.name}>
                    <LayerRow checked={!hidden.has(o.name)} onCheck={() => onToggle(o.name)} editing={editing === id} onEdit={() => edit(id)}
                      swatch={<i className={`sw sw-${o.style.shape ?? "point"}`} style={{ background: sw[0].color }} />} label={o.title} />
                    {editing === id && <VectorStyleEditor base={o.style} ov={styles.vectors[o.name] ?? {}} onChange={(p) => vecOv(o.name, p)} onReset={() => vecOv(o.name, null)} />}
                    {!hidden.has(o.name) && sw.length > 1 && (
                      <ul className="pw-legend">{sw.map((l) => <li key={l.label}><i style={{ background: l.color }} />{l.label}</li>)}</ul>
                    )}
                  </div>
                );
              })}
              {images.map((o) => {
                const id = `img:${o.name}`;
                const opacity = styles.images[o.name]?.opacity ?? 0.85;
                return (
                  <div key={o.name}>
                    <LayerRow checked={!hidden.has(o.name)} onCheck={() => onToggle(o.name)} editing={editing === id} onEdit={() => edit(id)}
                      swatch={<i className="sw sw-raster" />} label={o.title} />
                    {editing === id && (
                      <div className="pw-style">
                        <Opacity value={opacity} onChange={(v) => setStyles({ ...styles, images: { ...styles.images, [o.name]: { opacity: v } } })} />
                        <p className="muted pw-style-note">Colours of this result are fixed by the analysis.</p>
                      </div>
                    )}
                    {!hidden.has(o.name) && o.legend.length > 0 && (
                      <ul className="pw-legend">{o.legend.map((l) => <li key={l.label}><i style={{ background: l.color }} />{l.label}</li>)}</ul>
                    )}
                  </div>
                );
              })}
            </div>
          )}
          {run && run.status !== "done" && <p className="muted small pw-layer-note">Layers appear when run #{run.id} finishes.</p>}

          {satLayers.length > 0 && (
            <div className="pw-layer-group">
              <div className="pw-layer-group-head"><span>Data layers</span></div>
              {satLayers.map((l) => {
                const st = sat[l.id];
                const id = `sat:${l.id}`;
                const lg = effectiveLegend(l, st);
                return (
                  <div key={l.id}>
                    <div className="pw-layer">
                      <span className="pw-layer-name" title={l.desc}>{l.name}{st.year != null && <small className="muted"> · {st.year}</small>}</span>
                      {satLoading.has(l.id) && <span className="spin-dot" aria-label="Loading" />}
                      <StyleBtn active={editing === id} onClick={() => edit(id)} />
                      <button type="button" className="icon-btn icon-btn-xs" aria-label={`Remove ${l.name}`} title="Remove from map" onClick={() => setSat(toggleSat(sat, l))}><X aria-hidden="true" /></button>
                    </div>
                    {editing === id && <RasterStyleEditor layer={l} st={st} onChange={(p) => patchSat(l.id, p)} />}
                    <div className="pw-sat-legend"><SatLegendView legend={lg} /></div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="pw-layer-group">
            <LayerRow checked={showArea} onCheck={onToggleArea} editing={editing === "area"} onEdit={() => edit("area")}
              swatch={<i className="sw sw-area" style={{ borderColor: styles.area.color, background: hexA(styles.area.color, styles.area.fillOpacity) }} />} label="Area of influence" />
            {editing === "area" && (
              <div className="pw-style">
                <ColorRow label="Outline" value={styles.area.color} onChange={(color) => setStyles({ ...styles, area: { ...styles.area, color } })} />
                <Opacity label="Fill" value={styles.area.fillOpacity} min={0} onChange={(fillOpacity) => setStyles({ ...styles, area: { ...styles.area, fillOpacity } })} />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

const hexA = (hex: string, a: number) => `${hex}${Math.round(Math.max(0, Math.min(1, a)) * 255).toString(16).padStart(2, "0")}`;

function StyleBtn({ active, onClick }: { active: boolean; onClick: () => void }) {
  return (
    <button type="button" className={`icon-btn icon-btn-xs pw-style-btn${active ? " is-on" : ""}`} aria-expanded={active} aria-label="Layer style" title="Colours and opacity" onClick={onClick}>
      <Palette aria-hidden="true" />
    </button>
  );
}

function LayerRow({ checked, onCheck, editing, onEdit, swatch, label }: {
  checked: boolean; onCheck: () => void; editing: boolean; onEdit: () => void; swatch: ReactNode; label: string;
}) {
  return (
    <div className="pw-layer">
      <input type="checkbox" checked={checked} onChange={onCheck} aria-label={`Show ${label}`} />
      {swatch}
      <span className="pw-layer-name" title={label}>{label}</span>
      <StyleBtn active={editing} onClick={onEdit} />
    </div>
  );
}

function Opacity({ label = "Opacity", value, min = 0.05, onChange }: { label?: string; value: number; min?: number; onChange: (v: number) => void }) {
  return (
    <label className="pw-style-row"><span>{label}</span>
      <input type="range" min={min} max={1} step={0.05} value={value} onChange={(e) => onChange(Number(e.target.value))} />
      <em>{Math.round(value * 100)}%</em>
    </label>
  );
}

function ColorRow({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return <label className="pw-style-row"><span>{label}</span><input type="color" value={value} onChange={(e) => onChange(e.target.value)} /></label>;
}

function PalettePicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const base = value.endsWith("_r") ? value.slice(0, -2) : value;
  const rev = value.endsWith("_r");
  return (
    <>
      <label className="pw-style-row"><span>Palette</span>
        <select className="input" value={base} onChange={(e) => onChange(e.target.value + (rev ? "_r" : ""))}>
          {Object.entries(PALETTES).map(([k, p]) => <option key={k} value={k}>{p.label}</option>)}
        </select>
      </label>
      <div className="pw-style-ramp" style={{ background: cssGradient(value) }} />
      <label className="pw-style-check"><input type="checkbox" checked={rev} onChange={(e) => onChange(base + (e.target.checked ? "_r" : ""))} />Reverse</label>
    </>
  );
}

function RasterStyleEditor({ layer, st, onChange }: { layer: SatLayer; st: SatState[string]; onChange: (p: Partial<SatState[string]>) => void }) {
  const def = layer.style;
  const range = st.range ?? def?.range;
  if (isVectorTiles(layer)) {
    const min = st.threshold ?? 0;
    return (
      <div className="pw-style">
        <Opacity value={st.opacity} onChange={(opacity) => onChange({ opacity })} />
        <label className="pw-style-row"><span>Min. score</span>
          <input type="range" min={0} max={95} step={5} value={min} onChange={(e) => onChange({ threshold: Number(e.target.value) || undefined })} />
          <em>{min || "All"}</em>
        </label>
        <p className="muted pw-style-note">Zoomed out: field density. Fields show from zoom 9, filtered by model score. Drawn in full, not cut to the area.</p>
      </div>
    );
  }
  return (
    <div className="pw-style">
      <Opacity value={st.opacity} onChange={(opacity) => onChange({ opacity })} />
      {def && range ? (
        <>
          <PalettePicker value={st.cmap ?? def.cmap} onChange={(cmap) => onChange({ cmap })} />
          <div className="pw-style-row"><span>Range</span>
            <span className="pw-style-range">
              <NumberInput value={range[0]} onCommit={(v) => v < range[1] && onChange({ range: [v, range[1]] })} label="Minimum" />
              <span>to</span>
              <NumberInput value={range[1]} onCommit={(v) => v > range[0] && onChange({ range: [range[0], v] })} label="Maximum" />
            </span>
          </div>
          {(st.cmap || st.range) && (
            <button type="button" className="link-btn small pw-style-reset" onClick={() => onChange({ cmap: undefined, range: undefined })}><RotateCcw aria-hidden="true" />Default colours</button>
          )}
        </>
      ) : <p className="muted pw-style-note">{layer.view_only ? "A picture from an outside service: only its opacity can change." : "Classes keep their standard colours."}</p>}
    </div>
  );
}

/** A number field that applies on Enter or when it loses focus (each change redraws tiles). */
function NumberInput({ value, onCommit, label }: { value: number; onCommit: (v: number) => void; label: string }) {
  const [draft, setDraft] = useState<string | null>(null);
  const commit = () => { if (draft != null && draft.trim() !== "" && Number.isFinite(Number(draft))) onCommit(Number(draft)); setDraft(null); };
  return (
    <input className="input" type="number" aria-label={label} value={draft ?? String(value)}
      onChange={(e) => setDraft(e.target.value)} onBlur={commit} onKeyDown={(e) => { if (e.key === "Enter") commit(); }} />
  );
}

function VectorStyleEditor({ base, ov, onChange, onReset }: { base: VectorStyle; ov: VectorOverride; onChange: (p: Partial<VectorOverride>) => void; onReset: () => void }) {
  const classed = !!base.property && !!(base.classes?.length || base.steps?.length);
  const shape = base.shape ?? "point";
  return (
    <div className="pw-style">
      {classed
        ? <PalettePicker value={ov.palette ?? "viridis"} onChange={(palette) => onChange({ palette })} />
        : <ColorRow label="Colour" value={ov.color ?? base.color ?? "#0B3B47"} onChange={(color) => onChange({ color })} />}
      <Opacity value={ov.opacity ?? base.opacity ?? (shape === "polygon" ? 0.6 : 1)} onChange={(opacity) => onChange({ opacity })} />
      {shape !== "polygon" && (
        <label className="pw-style-row"><span>{shape === "line" ? "Width" : "Size"}</span>
          <input type="range" min={0.4} max={3} step={0.1} value={ov.size ?? 1} onChange={(e) => onChange({ size: Number(e.target.value) })} />
          <em>×{(ov.size ?? 1).toFixed(1)}</em>
        </label>
      )}
      {shape !== "line" && <ColorRow label="Outline" value={ov.outline ?? "#ffffff"} onChange={(outline) => onChange({ outline })} />}
      {Object.keys(ov).length > 0 && <button type="button" className="link-btn small pw-style-reset" onClick={onReset}><RotateCcw aria-hidden="true" />Default style</button>}
    </div>
  );
}

function toCsv(t: TableOut) {
  const esc = (v: unknown) => { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return [t.columns.map((c) => esc(c.label + (c.unit ? ` (${c.unit})` : ""))).join(","), ...t.rows.map((r) => t.columns.map((c) => esc(r[c.key])).join(","))].join("\n");
}

/** Wide tables slide up over the map instead of squeezing into the side panel. */
export function TableDrawer({ table, onClose }: { table: TableOut; onClose: () => void }) {
  const [tall, setTall] = useState(false);
  const csv = () => {
    const url = URL.createObjectURL(new Blob([toCsv(table)], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url; a.download = `${table.name}.csv`; a.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className={`pw-drawer${tall ? " is-tall" : ""}`} aria-label={table.title}>
      <header>
        <h3>{table.title} <span className="muted small">{table.rows.length} rows</span></h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={csv}><Download aria-hidden="true" />CSV</button>
        <button type="button" className="icon-btn" aria-label={tall ? "Shrink" : "Expand"} onClick={() => setTall((v) => !v)}>{tall ? <Minimize2 aria-hidden="true" /> : <Maximize2 aria-hidden="true" />}</button>
        <button type="button" className="icon-btn" aria-label="Close table" onClick={onClose}><X aria-hidden="true" /></button>
      </header>
      <div className="ptable-wrap">
        <table className="ptable">
          <thead><tr>{table.columns.map((c) => <th key={c.key}>{c.label}{c.unit ? ` (${c.unit})` : ""}</th>)}</tr></thead>
          <tbody>{table.rows.map((r, i) => <tr key={i}>{table.columns.map((c) => <td key={c.key}>{fmtNum(r[c.key])}</td>)}</tr>)}</tbody>
        </table>
      </div>
      {table.note && <p className="muted small pw-drawer-note">{table.note}</p>}
    </section>
  );
}
