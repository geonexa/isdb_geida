import { CircleAlert, CircleCheck, Clock, Download, LoaderCircle, MapPin, Play, Plus, Table2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { label } from "@/features/projects/data";
import type { CriteriaLayer, Criterion, DatasetInfo, Evidence, Meta, ModuleInfo, ModuleParam, PointPicker, Run, RunOutput } from "@/features/projects/types";
import { ACTIVE, fileUrl, fmtNum } from "@/features/projects/workspace/data";

export type TableOut = Extract<RunOutput, { type: "table" }>;

export function RunIcon({ status }: { status: Run["status"] }) {
  if (status === "done") return <CircleCheck className="ri ri-done" aria-label="Done" />;
  if (status === "failed") return <CircleAlert className="ri ri-failed" aria-label="Failed" />;
  if (status === "running") return <LoaderCircle className="ri ri-running" aria-label="Running" />;
  if (status === "cancelled") return <X className="ri" aria-label="Cancelled" />;
  return <Clock className="ri" aria-label="Queued" />;
}

/** "lon, lat" with 5 decimals (about 1 m). */
const fmtPoint = (ll: [number, number]) => `${ll[0].toFixed(5)}, ${ll[1].toFixed(5)}`;
/** [lon, lat] from typed text ("34.25, 2.31" or "34.25 2.31"), or null. */
export function parsePoint(text: string): [number, number] | null {
  const n = text.split(/[\s,;]+/).filter(Boolean).map(Number);
  if (n.length !== 2 || !n.every(Number.isFinite)) return null;
  return Math.abs(n[0]) <= 180 && Math.abs(n[1]) <= 90 ? [n[0], n[1]] : null;
}
const initial = (p: ModuleParam) => p.type === "point" ? (Array.isArray(p.default) ? fmtPoint(p.default as [number, number]) : "")
  : p.type === "criteria" ? JSON.stringify(p.default ?? []) : String(p.default ?? "");

/** Run form. Point parameters are picked on the project map (each click moves the marker) or typed. */
export function RunForm({ module, picker, onStart, onCancel }: {
  module: ModuleInfo; picker?: PointPicker; onStart: (p: Record<string, string>) => void; onCancel: () => void;
}) {
  const [vals, setVals] = useState<Record<string, string>>(Object.fromEntries(module.parameters.map((p) => [p.name, initial(p)])));
  const points = module.parameters.filter((p) => p.type === "point");
  const [active, setActive] = useState<string | undefined>(points[0]?.name);
  const activeValue = active ? vals[active] : "";
  // While the form is open, map clicks set the active point.
  useEffect(() => {
    if (!picker || !active) return;
    picker.start((ll) => setVals((v) => ({ ...v, [active]: fmtPoint(ll) })));
    return () => picker.stop();
  }, [picker, active]);
  useEffect(() => { if (picker && active) picker.show(parsePoint(activeValue)); }, [picker, active, activeValue]);
  useEffect(() => () => picker?.show(null), [picker]);
  const missing = points.filter((p) => !parsePoint(vals[p.name]));
  const data = module.inputs.filter((i) => i.dataset);
  return (
    <form className="run-form" onSubmit={(e) => { e.preventDefault(); if (!missing.length) onStart(vals); }}>
      {module.parameters.map((p) => p.type === "criteria" ? (
        <div key={p.name} className="run-criteria-field">
          <span className="run-field-label">{p.label}</span>
          <CriteriaEditor layers={p.layers ?? []} value={vals[p.name]} onChange={(v) => setVals({ ...vals, [p.name]: v })} />
        </div>
      ) : (
        <label key={p.name}>{p.label}
          {p.type === "choice" ? (
            <select className="input" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}>
              {p.choices!.map((c) => <option key={String(c.value)} value={String(c.value)}>{c.label}</option>)}
            </select>
          ) : p.type === "point" ? (
            <>
              <span className={`run-point${active === p.name ? " is-active" : ""}`}>
                <MapPin aria-hidden="true" />
                <input className="input" placeholder="Click the map, or type longitude, latitude" value={vals[p.name]}
                  aria-invalid={vals[p.name] !== "" && !parsePoint(vals[p.name])}
                  onFocus={() => setActive(p.name)} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} />
              </span>
              <span className="muted small">{picker ? "Click the map to place it; each click moves it." : "Longitude, latitude in degrees."}</span>
            </>
          ) : (
            <input className="input" inputMode="decimal" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} />
          )}
        </label>
      ))}
      {/* Short list only: modules that read many layers (e.g. an area profile) already show them as tags above. */}
      {data.length > 0 && data.length <= 3 && <p className="muted small">Data: {data.map((i) => i.dataset!.title).join(", ")} — fetched for the project area and cached.</p>}
      <div className="run-form-actions">
        <button className="btn btn-dark btn-sm" disabled={missing.length > 0} title={missing.length ? `Pick ${missing[0].label.toLowerCase()} on the map first` : undefined}><Play aria-hidden="true" />Start</button>
        <button type="button" className="btn btn-outline btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

/** "2018, 2019, 2020, 2022" -> "2018–2020, 2022". */
function yearRanges(years: number[]) {
  const ys = [...new Set(years)].sort((a, b) => a - b);
  const out: string[] = [];
  for (let i = 0; i < ys.length; i++) {
    let j = i;
    while (j + 1 < ys.length && ys[j + 1] === ys[j] + 1) j++;
    out.push(j > i ? `${ys[i]}–${ys[j]}` : String(ys[i]));
    i = j;
  }
  return out.join(", ");
}

/** A run's datasets, one line per dataset: the years it was read for (as ranges) and its licence. */
function dataSources(datasets: DatasetInfo[]) {
  const by = new Map<string, { dates: string[]; licence: string }>();
  for (const d of datasets) {
    const e = by.get(d.title) ?? { dates: [], licence: "" };
    if (d.reference_date) e.dates.push(d.reference_date);
    e.licence ||= d.licence;
    by.set(d.title, e);
  }
  return [...by].map(([title, { dates, licence }]) => {
    const years = dates.every((x) => /^\d{4}$/.test(x)) ? yearRanges(dates.map(Number)) : [...new Set(dates)].join(", ");
    return { title, extra: [years, licence].filter(Boolean).join("; ") };
  });
}

/**
 * Conditions for site suitability: a layer, its limits (min / max) or classes, a weight and "must-have".
 * The value is kept as JSON text in the form (the API checks it again).
 */
function CriteriaEditor({ layers, value, onChange }: { layers: CriteriaLayer[]; value: string; onChange: (v: string) => void }) {
  let rows: Criterion[] = [];
  try { rows = JSON.parse(value || "[]"); } catch { rows = []; }
  const byId = new Map(layers.map((l) => [l.id, l]));
  const groups = [...new Set(layers.map((l) => l.group || ""))];
  const set = (next: Criterion[]) => onChange(JSON.stringify(next));
  const patch = (i: number, p: Partial<Criterion>) => set(rows.map((r, j) => (j === i ? { ...r, ...p } : r)));
  const num = (s: string) => (s.trim() === "" ? null : Number(s));
  const total = rows.reduce((a, r) => a + (Number(r.weight) || 0), 0);
  const addRow = () => {
    const used = new Set(rows.map((r) => r.layer));
    const l = layers.find((x) => !used.has(x.id)) ?? layers[0];
    set([...rows, l.kind === "classes" ? { layer: l.id, classes: [], weight: 10, must: false } : { layer: l.id, min: null, max: null, weight: 10, must: false }]);
  };
  return (
    <div className="crit">
      {rows.map((r, i) => {
        const l = byId.get(r.layer);
        return (
          <div key={i} className="crit-row">
            <div className="crit-head">
              <select className="input" aria-label={`Condition ${i + 1} layer`} value={r.layer}
                onChange={(e) => { const nl = byId.get(e.target.value)!; patch(i, nl.kind === "classes" ? { layer: nl.id, classes: [], min: undefined, max: undefined } : { layer: nl.id, classes: undefined, min: null, max: null }); }}>
                {groups.map((g) => (
                  <optgroup key={g} label={g || "Layers"}>
                    {layers.filter((x) => (x.group || "") === g).map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
                  </optgroup>
                ))}
              </select>
              <button type="button" className="icon-btn icon-btn-xs" aria-label={`Remove condition ${i + 1}`} title="Remove" onClick={() => set(rows.filter((_, j) => j !== i))}><X aria-hidden="true" /></button>
            </div>
            {l?.kind === "classes" ? (
              <div className="crit-classes" role="group" aria-label="Classes that are suitable">
                {(l.classes ?? []).map((c) => {
                  const on = (r.classes ?? []).map(String).includes(String(c.value));
                  return (
                    <label key={String(c.value)} className={`crit-chip${on ? " is-on" : ""}`}>
                      <input type="checkbox" checked={on} onChange={() => patch(i, { classes: on ? (r.classes ?? []).filter((v) => String(v) !== String(c.value)) : [...(r.classes ?? []), c.value] })} />
                      {c.label}
                    </label>
                  );
                })}
              </div>
            ) : (
              <div className="crit-range">
                <span>from</span>
                <input className="input" inputMode="decimal" aria-label="Minimum" placeholder="no minimum" value={r.min ?? ""} onChange={(e) => patch(i, { min: num(e.target.value) })} />
                <span>to</span>
                <input className="input" inputMode="decimal" aria-label="Maximum" placeholder="no maximum" value={r.max ?? ""} onChange={(e) => patch(i, { max: num(e.target.value) })} />
                <span className="crit-unit">{l?.unit}</span>
              </div>
            )}
            <div className="crit-foot">
              <label className="crit-weight">Weight
                <input className="input" inputMode="decimal" aria-label="Weight" value={r.weight} onChange={(e) => patch(i, { weight: Number(e.target.value) || 0 })} />
                <span>{total > 0 ? `= ${Math.round((100 * (Number(r.weight) || 0)) / total)}%` : ""}</span>
              </label>
              <label className="crit-must" title="Land failing a must-have is excluded, whatever else it meets">
                <input type="checkbox" checked={!!r.must} onChange={(e) => patch(i, { must: e.target.checked })} />Must-have
              </label>
            </div>
          </div>
        );
      })}
      <div className="crit-actions">
        <button type="button" className="btn btn-outline btn-sm" onClick={addRow}><Plus aria-hidden="true" />Add condition</button>
        <span className="muted small">{rows.length} condition{rows.length === 1 ? "" : "s"} · weights scaled to 100%</span>
      </div>
    </div>
  );
}

/** Run results for the side panel: metrics, summary, evidence, tables (opened in the drawer), files. */
export function RunResult({ run, meta, canReview, onReview, onOpenTable }: {
  run: Run; meta?: Meta; canReview: boolean;
  onReview: (e: Evidence, a: "accept" | "reject") => void; onOpenTable: (t: TableOut) => void;
}) {
  const [showLog, setShowLog] = useState(false);
  const [showData, setShowData] = useState(false);
  const sources = run.status === "done" ? dataSources(run.datasets ?? []) : [];
  const outs = run.outputs ?? [];
  const metrics = outs.filter((o) => o.type === "metric") as Extract<RunOutput, { type: "metric" }>[];
  const tables = outs.filter((o) => o.type === "table") as TableOut[];
  // Downloads: every output with a file; raster results as their GeoTIFF values (not the map preview).
  const files = outs.flatMap((o) => o.type === "raster" ? [{ name: o.name, title: `${o.title} (GeoTIFF)`, file: o.data_file }]
    : "file" in o ? [o as { name: string; title: string; file: string }] : []);
  return (
    <div className="run-result">
      <p className="muted small">v{run.module_version} · run #{run.id} · {run.instrument} · {new Date(run.created).toLocaleString()} · {run.created_by}</p>
      {Object.keys(run.params).length > 0 && <p className="run-params">{Object.entries(run.params).map(([k, v]) => <span key={k}>{k.replace(/_/g, " ")}: <strong>{Array.isArray(v) && typeof v[0] === "object" ? `${v.length} condition${v.length === 1 ? "" : "s"}` : String(v)}</strong></span>)}</p>}
      {ACTIVE.has(run.status) && (
        <div className="run-progress"><div style={{ width: `${Math.max(3, run.progress)}%` }} /><span>{run.status === "queued" ? "Queued — waiting for the analysis worker" : `Running… ${run.progress}%`}</span></div>
      )}
      {run.status === "failed" && <div className="alert alert-error"><CircleAlert aria-hidden="true" /><div>{run.error}</div></div>}
      {run.status === "done" && (
        <>
          {metrics.length > 0 && <dl className="metrics">{metrics.map((m) => <div key={m.name}><dt>{m.title}</dt><dd>{fmtNum(m.value)}<span>{m.unit}</span></dd></div>)}</dl>}
          {run.summary && <p className="run-summary">{run.summary}</p>}
          {(run.evidence ?? []).length > 0 && (
            <section>
              <h4 className="pw-h4">Evidence for indicators</h4>
              <EvidenceList items={run.evidence!} meta={meta} canReview={canReview} onReview={onReview} />
            </section>
          )}
          {tables.length > 0 && (
            <section>
              <h4 className="pw-h4">Tables</h4>
              <ul className="pw-links">{tables.map((t) => (
                <li key={t.name}><button type="button" className="pw-link" onClick={() => onOpenTable(t)}><Table2 aria-hidden="true" />{t.title}<span className="muted small">{t.rows.length} rows</span></button></li>
              ))}</ul>
            </section>
          )}
          {files.length > 0 && (
            <section>
              <h4 className="pw-h4">Downloads</h4>
              <ul className="pw-links">{files.map((f) => (
                <li key={f.name}><a className="pw-link" href={`${fileUrl(run.id, f.file)}?download=1`}><Download aria-hidden="true" />{f.title}</a></li>
              ))}</ul>
            </section>
          )}
        </>
      )}
      {(sources.length > 0 || run.log) && (
        <div className="run-toggles">
          {sources.length > 0 && <button type="button" className="link-btn small" aria-expanded={showData} onClick={() => setShowData((v) => !v)}>{showData ? "Hide" : "Show"} data sources ({sources.length})</button>}
          {run.log && <button type="button" className="link-btn small" aria-expanded={showLog} onClick={() => setShowLog((v) => !v)}>{showLog ? "Hide" : "Show"} run log</button>}
        </div>
      )}
      {showData && (
        <ul className="run-data">{sources.map((d) => (
          <li key={d.title}><strong>{d.title}</strong>{d.extra && <span className="muted"> · {d.extra}</span>}</li>
        ))}</ul>
      )}
      {showLog && <pre className="run-log">{run.log}</pre>}
    </div>
  );
}

/** Evidence as cards: fits the narrow side panel. */
export function EvidenceList({ items, meta, canReview, onReview, onOpenRun }: {
  items: Evidence[]; meta?: Meta; canReview: boolean; onReview: (e: Evidence, a: "accept" | "reject") => void; onOpenRun?: (run: number) => void;
}) {
  return (
    <ul className="ev-list">
      {items.map((e) => (
        <li key={e.id} className={`ev-card is-${e.status}`}>
          <div className="ev-top">
            <span className="cri-tag is-match">CRI {e.cri}</span>
            <span className={`role role-${e.role}`}>{label(meta?.geo_roles, e.role)}</span>
            <span className="ev-inst">{e.instrument}</span>
          </div>
          <p className="ev-value">{e.value != null ? e.value.toLocaleString() : "—"} <span>{e.unit}</span></p>
          <p className="ev-label">{e.label}</p>
          <p className="muted small">{e.indicator_statement ? `For: ${e.indicator_statement}` : "No matching indicator in the Results Framework"}{e.reference_date ? ` · data ${e.reference_date}` : ""}</p>
          {e.caveats && <p className="ev-caveat">{e.caveats}</p>}
          <div className="ev-actions">
            {e.status === "proposed" && canReview ? (
              <>
                <button type="button" className="btn btn-dark btn-sm" onClick={() => onReview(e, "accept")}>Accept</button>
                <button type="button" className="btn btn-outline btn-sm" onClick={() => onReview(e, "reject")}>Reject</button>
              </>
            ) : (
              <span className={`pchip pchip-${e.status === "accepted" ? "published" : e.status === "rejected" ? "error" : "review"}`}>{e.status}{e.reviewed_by ? ` · ${e.reviewed_by}` : ""}</span>
            )}
            {onOpenRun && <button type="button" className="link-btn small" onClick={() => onOpenRun(e.run)}>run #{e.run}</button>}
          </div>
        </li>
      ))}
    </ul>
  );
}
