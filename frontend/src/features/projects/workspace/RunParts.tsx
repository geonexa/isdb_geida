import { CircleAlert, CircleCheck, Clock, Download, LoaderCircle, Play, Table2, X } from "lucide-react";
import { useState } from "react";

import { label } from "@/features/projects/data";
import type { Evidence, Meta, ModuleInfo, Run, RunOutput } from "@/features/projects/types";
import { ACTIVE, fileUrl, fmtNum } from "@/features/projects/workspace/data";

export type TableOut = Extract<RunOutput, { type: "table" }>;

export function RunIcon({ status }: { status: Run["status"] }) {
  if (status === "done") return <CircleCheck className="ri ri-done" aria-label="Done" />;
  if (status === "failed") return <CircleAlert className="ri ri-failed" aria-label="Failed" />;
  if (status === "running") return <LoaderCircle className="ri ri-running" aria-label="Running" />;
  if (status === "cancelled") return <X className="ri" aria-label="Cancelled" />;
  return <Clock className="ri" aria-label="Queued" />;
}

export function RunForm({ module, onStart, onCancel }: { module: ModuleInfo; onStart: (p: Record<string, string>) => void; onCancel: () => void }) {
  const [vals, setVals] = useState<Record<string, string>>(Object.fromEntries(module.parameters.map((p) => [p.name, String(p.default)])));
  const data = module.inputs.filter((i) => i.dataset);
  return (
    <form className="run-form" onSubmit={(e) => { e.preventDefault(); onStart(vals); }}>
      {module.parameters.map((p) => (
        <label key={p.name}>{p.label}
          {p.type === "choice" ? (
            <select className="input" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}>
              {p.choices!.map((c) => <option key={String(c.value)} value={String(c.value)}>{c.label}</option>)}
            </select>
          ) : (
            <input className="input" inputMode="decimal" value={vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} />
          )}
        </label>
      ))}
      {/* Short list only: modules that read many layers (e.g. an area profile) already show them as tags above. */}
      {data.length > 0 && data.length <= 3 && <p className="muted small">Data: {data.map((i) => i.dataset!.title).join(", ")} — fetched for the project area and cached.</p>}
      <div className="run-form-actions">
        <button className="btn btn-dark btn-sm"><Play aria-hidden="true" />Start</button>
        <button type="button" className="btn btn-outline btn-sm" onClick={onCancel}>Cancel</button>
      </div>
    </form>
  );
}

/** Run results for the side panel: metrics, summary, evidence, tables (opened in the drawer), files. */
export function RunResult({ run, meta, canReview, onReview, onOpenTable }: {
  run: Run; meta?: Meta; canReview: boolean;
  onReview: (e: Evidence, a: "accept" | "reject") => void; onOpenTable: (t: TableOut) => void;
}) {
  const [showLog, setShowLog] = useState(false);
  const outs = run.outputs ?? [];
  const metrics = outs.filter((o) => o.type === "metric") as Extract<RunOutput, { type: "metric" }>[];
  const tables = outs.filter((o) => o.type === "table") as TableOut[];
  const files = outs.filter((o) => "file" in o) as { name: string; title: string; file: string }[];
  return (
    <div className="run-result">
      <p className="muted small">v{run.module_version} · run #{run.id} · {run.instrument} · {new Date(run.created).toLocaleString()} · {run.created_by}</p>
      {Object.keys(run.params).length > 0 && <p className="run-params">{Object.entries(run.params).map(([k, v]) => <span key={k}>{k.replace(/_/g, " ")}: <strong>{String(v)}</strong></span>)}</p>}
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
          {(run.datasets ?? []).length > 0 && <p className="muted small">Data: {run.datasets!.map((d) => `${d.title} (${d.reference_date}; ${d.licence})`).join(" · ")}</p>}
        </>
      )}
      {run.log && <button type="button" className="link-btn small" onClick={() => setShowLog((v) => !v)}>{showLog ? "Hide" : "Show"} run log</button>}
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
