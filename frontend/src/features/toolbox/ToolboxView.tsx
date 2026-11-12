import "@/features/toolbox/toolbox.css";

import { useQuery, useQueryClient, type UseQueryResult } from "@tanstack/react-query";
import {
  ArrowLeft, ChevronDown, CircleAlert, CircleCheck, Clock, Download, Eye, EyeOff, FileUp, LoaderCircle, Pencil, Play,
  Search, Trash2, X,
} from "lucide-react";
import { useRef, useState } from "react";

import { toolFileUrl, type ToolLayer } from "@/features/projects/workspace/toolResults";
import { api, ApiError, upload } from "@/shared/api/client";
import { useConfirm } from "@/shared/components/Confirm";
import { useToast } from "@/shared/components/Toasts";

/* ------------------------------------------------------------------ API types */
type FormParam = {
  name: string; label: string; description: string; required: boolean;
  kind: "layer" | "choice" | "bool" | "number" | "text";
  layer_kind?: "vector" | "raster" | "table"; multiple?: boolean;
  choices?: (string | number)[]; integer?: boolean; default?: unknown;
};
type Tool = { id: string; title: string; summary: string; params: FormParam[]; engine: string };
type Catalog = { categories: { id: string; title: string; icon: string; tools: Tool[] }[]; count: number; engine: string };
type InputRef = Record<string, string | number>;
type InputOption = { ref: InputRef; label: string; kind: "vector" | "raster" | "table"; group: string; years?: number[] };
type Output = {
  name: string; title: string; kind: "vector" | "raster" | "table" | "file"; file: string;
  geojson?: string; preview?: string; bounds?: [number, number, number, number]; legend?: { label: string; color: string }[];
  features?: number; geometry?: string; fields?: string[]; style?: { color?: string };
  columns?: string[]; rows?: string[][]; row_count?: number; stats?: Record<string, number>; resolution_m?: number;
};
type ToolRunT = {
  id: number; tool: string; tool_title: string; engine: string; name: string; status: "queued" | "running" | "done" | "failed";
  error: string; created: string; finished: string | null; created_by: string; size_bytes: number; outputs: Output[];
  can_delete: boolean; report?: Record<string, unknown> | null; log?: string; params?: Record<string, unknown>;
};
type Upload = { id: number; name: string; kind: string; size_bytes: number; info: Record<string, unknown>; created: string; created_by: string; can_delete: boolean };

const ACTIVE = new Set(["queued", "running"]);
/** A stable key for an input reference, without its year (the year is chosen beside the layer). */
const refKey = (r: InputRef) => JSON.stringify(Object.keys(r).filter((k) => k !== "year").sort().map((k) => [k, r[k]]));
const fmtBytes = (b: number) => b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`;
const when = (iso: string) => new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
const fmt = (v: unknown) => typeof v === "number" ? (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : Number(v.toPrecision(4)).toString()) : String(v ?? "—");

type Props = {
  code: string; canRun: boolean;
  /** Results on the map, and how to add / remove them. */
  shown: ToolLayer[]; onShow: (l: ToolLayer) => void; onHide: (id: string) => void; onRunDeleted: (run: number) => void;
};

/**
 * Processing toolbox: general vector and raster tools (GeoLibre, run on the server, plus GEIDA's own) on the
 * project's layers. Every run is saved with its settings and results; results can be shown on the map,
 * downloaded, used as inputs to other tools, renamed and deleted. Uploaded files are kept with the project.
 */
export function ToolboxView({ code, canRun, shown, onShow, onHide, onRunDeleted }: Props) {
  const [view, setView] = useState<"tools" | "results" | "files">("tools");
  const [tool, setTool] = useState<Tool | null>(null);
  const catalog = useQuery({ queryKey: ["tb-tools"], queryFn: () => api<Catalog>("/api/toolbox/tools/"), staleTime: Infinity });
  const runs = useQuery({
    queryKey: ["tb-runs", code], queryFn: () => api<{ runs: ToolRunT[] }>(`/api/toolbox/${code}/runs/`).then((r) => r.runs),
    refetchInterval: (q) => ((q.state.data ?? []).some((r) => ACTIVE.has(r.status)) ? 2000 : false),
  });
  const uploads = useQuery({ queryKey: ["tb-uploads", code], queryFn: () => api<{ uploads: Upload[] }>(`/api/toolbox/${code}/uploads/`).then((r) => r.uploads) });
  const active = (runs.data ?? []).filter((r) => ACTIVE.has(r.status)).length;

  return (
    <div className="tbx">
      <div className="tbx-tabs" role="tablist" aria-label="Toolbox">
        <button type="button" role="tab" aria-selected={view === "tools"} onClick={() => setView("tools")}>Tools{catalog.data && <em>{catalog.data.count}</em>}</button>
        <button type="button" role="tab" aria-selected={view === "results"} onClick={() => setView("results")}>
          Results{(runs.data ?? []).length > 0 && <em>{runs.data!.length}</em>}{active > 0 && <LoaderCircle className="spin" aria-label={`${active} running`} />}
        </button>
        <button type="button" role="tab" aria-selected={view === "files"} onClick={() => setView("files")}>Files{(uploads.data ?? []).length > 0 && <em>{uploads.data!.length}</em>}</button>
      </div>
      {view === "tools" && (tool
        ? <ToolForm code={code} tool={tool} canRun={canRun} onBack={() => setTool(null)} onStarted={() => { setTool(null); setView("results"); }} />
        : <ToolList catalog={catalog} onPick={setTool} />)}
      {view === "results" && <Results code={code} runs={runs.data} loading={runs.isPending} shown={shown} onShow={onShow} onHide={onHide} onRunDeleted={onRunDeleted} />}
      {view === "files" && <Files code={code} canRun={canRun} uploads={uploads.data} />}
    </div>
  );
}

/* ------------------------------------------------------------------ tool list */
function ToolList({ catalog, onPick }: { catalog: UseQueryResult<Catalog>; onPick: (t: Tool) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  if (catalog.isError) return <p className="field-error"><CircleAlert aria-hidden="true" />{(catalog.error as Error).message}</p>;
  if (!catalog.data) return <p className="muted">Loading the tools…</p>;
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const match = (t: Tool) => words.every((w) => `${t.title} ${t.summary} ${t.id}`.toLowerCase().includes(w));
  return (
    <div className="tbx-list">
      <p className="muted small">{catalog.data.count} tools for vector and raster data, run on the server ({catalog.data.engine}). Every run is saved under Results.</p>
      <label className="tbx-search"><Search aria-hidden="true" /><input type="search" placeholder="Search tools (buffer, clip, zonal…)" value={q} onChange={(e) => setQ(e.target.value)} /></label>
      {catalog.data.categories.map((c) => {
        const tools = c.tools.filter(match);
        if (!tools.length) return null;
        const isOpen = words.length > 0 || open === c.id;
        return (
          <section key={c.id} className={`tbx-cat${isOpen ? " is-open" : ""}`}>
            <button type="button" className="tbx-cat-head" aria-expanded={isOpen} onClick={() => setOpen(open === c.id ? null : c.id)}>
              <span>{c.title}</span><em>{tools.length}</em><ChevronDown aria-hidden="true" />
            </button>
            {isOpen && (
              <ul>{tools.map((t) => (
                <li key={t.id}><button type="button" className="tbx-tool" onClick={() => onPick(t)}>
                  <strong>{t.title}</strong><span>{t.summary}</span>
                </button></li>
              ))}</ul>
            )}
          </section>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ tool form */
function ToolForm({ code, tool, canRun, onBack, onStarted }: { code: string; tool: Tool; canRun: boolean; onBack: () => void; onStarted: () => void }) {
  const toast = useToast();
  const qc = useQueryClient();
  const inputs = useQuery({ queryKey: ["tb-inputs", code], queryFn: () => api<{ inputs: InputOption[] }>(`/api/toolbox/${code}/inputs/`).then((r) => r.inputs) });
  const [vals, setVals] = useState<Record<string, unknown>>(() => Object.fromEntries(tool.params.filter((p) => p.kind !== "layer" && p.default != null).map((p) => [p.name, p.default])));
  const [layers, setLayers] = useState<Record<string, InputRef[]>>({});
  const [name, setName] = useState(tool.title);
  const [busy, setBusy] = useState(false);
  const [more, setMore] = useState(false);
  const required = tool.params.filter((p) => p.required);
  const optional = tool.params.filter((p) => !p.required);

  async function run() {
    for (const p of required) {
      if (p.kind === "layer" ? !(layers[p.name] ?? []).length : vals[p.name] == null || vals[p.name] === "") {
        toast(`${p.kind === "layer" ? "Choose a layer for" : "Enter a value for"} ${p.label.toLowerCase()}.`, "error");
        return;
      }
    }
    const params: Record<string, unknown> = {};
    for (const p of tool.params) {
      if (p.kind === "layer") continue;
      const v = vals[p.name];
      if (v == null || v === "") continue;
      params[p.name] = p.kind === "number" ? Number(v) : v;
    }
    const ins = Object.fromEntries(Object.entries(layers).filter(([, v]) => v.length).map(([k, v]) => {
      const p = tool.params.find((x) => x.name === k);
      return [k, p?.multiple ? v : v[0]];
    }));
    setBusy(true);
    try {
      await api(`/api/toolbox/${code}/runs/`, { method: "POST", body: { tool: tool.id, params, inputs: ins, name } });
      toast(`${tool.title} started. It appears under Results.`, "success");
      qc.invalidateQueries({ queryKey: ["tb-runs", code] });
      onStarted();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't start the tool.", "error");
    } finally { setBusy(false); }
  }

  const field = (p: FormParam) => (
    <div key={p.name} className="tbx-field">
      <label htmlFor={`tbx-${p.name}`}>{p.label}{p.required && <span className="tbx-req" aria-label="required">*</span>}</label>
      {p.kind === "layer" ? (
        <LayerPicker id={`tbx-${p.name}`} param={p} options={inputs.data} value={layers[p.name] ?? []} onChange={(v) => setLayers({ ...layers, [p.name]: v })} />
      ) : p.kind === "choice" ? (
        <select id={`tbx-${p.name}`} className="input" value={String(vals[p.name] ?? "")} onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })}>
          {!p.required && <option value="">(default)</option>}
          {(p.choices ?? []).map((c) => <option key={String(c)} value={String(c)}>{String(c)}</option>)}
        </select>
      ) : p.kind === "bool" ? (
        <input id={`tbx-${p.name}`} type="checkbox" checked={!!vals[p.name]} onChange={(e) => setVals({ ...vals, [p.name]: e.target.checked })} />
      ) : (
        <input id={`tbx-${p.name}`} className="input" inputMode={p.kind === "number" ? "decimal" : undefined} value={String(vals[p.name] ?? "")}
          onChange={(e) => setVals({ ...vals, [p.name]: e.target.value })} />
      )}
      {p.description && <p className="tbx-hint">{p.description}</p>}
    </div>
  );

  return (
    <div className="tbx-form">
      <div className="tbx-form-head">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Back to tools" title="Back"><ArrowLeft aria-hidden="true" /></button>
        <div><h3>{tool.title}</h3><p className="muted small">{tool.summary}</p></div>
      </div>
      {inputs.isPending && <p className="muted small">Loading the project's layers…</p>}
      {required.map(field)}
      {optional.length > 0 && (
        <>
          <button type="button" className="link-btn small" aria-expanded={more} onClick={() => setMore((v) => !v)}>{more ? "Hide" : "Show"} optional settings ({optional.length})</button>
          {more && optional.map(field)}
        </>
      )}
      <div className="tbx-field">
        <label htmlFor="tbx-name">Result name</label>
        <input id="tbx-name" className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </div>
      <p className="tbx-hint">Inputs are taken for the extent of the area of influence (its bounding box plus 1 km) and put in its UTM zone, so distances and areas are in metres. Use Clip to keep only what is inside the area.</p>
      <div className="tbx-actions">
        <button type="button" className="btn btn-dark" disabled={!canRun || busy} onClick={run} title={canRun ? undefined : "Only the project's owner or a reviewer can run tools"}>
          {busy ? <LoaderCircle className="spin" aria-hidden="true" /> : <Play aria-hidden="true" />}Run
        </button>
      </div>
    </div>
  );
}

function LayerPicker({ id, param, options, value, onChange }: {
  id: string; param: FormParam; options?: InputOption[]; value: InputRef[]; onChange: (v: InputRef[]) => void;
}) {
  const list = (options ?? []).filter((o) => o.kind === param.layer_kind);
  if (options && !list.length) {
    return <p className="tbx-hint">No {param.layer_kind} layers yet. {param.layer_kind === "table" ? "Upload a CSV under Files." : "Run an analysis or upload a file under Files."}</p>;
  }
  const groups = [...new Set(list.map((o) => o.group))];
  const byKey = new Map(list.map((o) => [refKey(o.ref), o]));
  const set = (i: number, r: InputRef | null) => {
    const next = [...value];
    if (r) next[i] = r; else next.splice(i, 1);
    onChange(next.filter(Boolean));
  };
  const one = (r: InputRef | undefined, i: number) => {
    const opt = r ? byKey.get(refKey(r)) : undefined;
    return (
      <div key={i} className="tbx-layer">
        <select id={i === 0 ? id : undefined} className="input" value={r ? refKey(r) : ""}
          onChange={(e) => {
            const o = byKey.get(e.target.value);
            set(i, o ? (o.years?.length ? { ...o.ref, year: o.years[o.years.length - 1] } : o.ref) : null);
          }}>
          <option value="">{param.multiple && i > 0 ? "Add another layer…" : "Choose a layer…"}</option>
          {groups.map((g) => (
            <optgroup key={g} label={g}>
              {list.filter((o) => o.group === g).map((o) => <option key={refKey(o.ref)} value={refKey(o.ref)}>{o.label}</option>)}
            </optgroup>
          ))}
        </select>
        {opt?.years?.length ? (
          <select className="input tbx-year" aria-label="Year" value={String(r?.year ?? "")} onChange={(e) => set(i, { ...r!, year: Number(e.target.value) })}>
            {opt.years.map((y) => <option key={y} value={y}>{y}</option>)}
          </select>
        ) : null}
      </div>
    );
  };
  return (
    <div className="tbx-layers">
      {(value.length ? value : [undefined]).map((r, i) => one(r, i))}
      {param.multiple && value.length > 0 && one(undefined, value.length)}
    </div>
  );
}

/* ------------------------------------------------------------------ results */
function Results({ code, runs, loading, shown, onShow, onHide, onRunDeleted }: {
  code: string; runs?: ToolRunT[]; loading: boolean; shown: ToolLayer[];
  onShow: (l: ToolLayer) => void; onHide: (id: string) => void; onRunDeleted: (run: number) => void;
}) {
  const confirm = useConfirm();
  const toast = useToast();
  const qc = useQueryClient();
  const [openId, setOpenId] = useState<number | null>(null);
  const [selecting, setSelecting] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  if (loading) return <p className="muted">Loading results…</p>;
  if (!runs?.length) return <p className="muted">No results yet. Pick a tool under Tools; every run is saved here.</p>;
  const deletable = runs.filter((r) => r.can_delete);
  const shownIds = new Set(shown.map((l) => l.id));

  async function remove(list: ToolRunT[]) {
    const one = list.length === 1;
    const bytes = list.reduce((s, r) => s + r.size_bytes, 0);
    if (!(await confirm({
      title: one ? `Delete "${list[0].name}"?` : `Delete ${list.length} results?`,
      message: `The result files${bytes ? ` (${fmtBytes(bytes)})` : ""} are removed and taken off the map. Tools that used ${one ? "it" : "them"} as input keep their own results. The project's Activity log records the deletion. This can't be undone.`,
      confirmLabel: one ? "Delete" : `Delete ${list.length}`, tone: "danger",
    }))) return;
    try {
      const res = await api<{ deleted: { id: number }[]; refused?: { reason: string }[] }>(
        one ? `/api/toolbox/runs/${list[0].id}/` : "/api/toolbox/runs/delete/", one ? { method: "DELETE" } : { method: "POST", body: { ids: list.map((r) => r.id) } });
      res.deleted.forEach((d) => onRunDeleted(d.id));
      if (res.deleted.length) toast(res.deleted.length === 1 ? "Result deleted." : `${res.deleted.length} results deleted.`, "success");
      (res.refused ?? []).forEach((r) => toast(r.reason, "error"));
      setPicked(new Set()); setSelecting(false);
      qc.invalidateQueries({ queryKey: ["tb-runs", code] });
      qc.invalidateQueries({ queryKey: ["tb-inputs", code] });
      qc.invalidateQueries({ queryKey: ["project", code] });
    } catch (e) { toast(e instanceof ApiError ? e.message : "Couldn't delete.", "error"); }
  }

  async function rename(r: ToolRunT) {
    const next = window.prompt("Name of this result", r.name)?.trim();
    if (!next || next === r.name) return;
    try {
      await api(`/api/toolbox/runs/${r.id}/`, { method: "PATCH", body: { name: next } });
      qc.invalidateQueries({ queryKey: ["tb-runs", code] });
    } catch (e) { toast(e instanceof ApiError ? e.message : "Couldn't rename.", "error"); }
  }

  const layerOf = (r: ToolRunT, o: Output): ToolLayer => ({
    id: `${r.id}:${o.name}`, run: r.id, name: r.outputs.length > 1 ? `${r.name} · ${o.title}` : r.name, source: `${r.tool_title} · #${r.id}`,
    kind: o.kind === "raster" ? "raster" : "vector",
    url: toolFileUrl(r.id, o.kind === "raster" ? o.preview! : o.geojson!), bounds: o.bounds,
    legend: o.kind === "raster" ? o.legend ?? [] : [], color: o.style?.color,
    download: toolFileUrl(r.id, o.file), downloadLabel: o.kind === "raster" ? "GeoTIFF" : "GeoPackage",
    opacity: 0.85, visible: true,
  });

  return (
    <div className="tbx-results">
      <div className="tbx-results-head">
        <span className="muted small">{runs.length} saved result{runs.length === 1 ? "" : "s"}</span>
        {deletable.length > 0 && <button type="button" className="link-btn small" onClick={() => { setSelecting((v) => !v); setPicked(new Set()); }}>{selecting ? "Done" : "Select"}</button>}
      </div>
      {selecting && (
        <div className="pw-runs-bulk">
          <label><input type="checkbox" checked={picked.size > 0 && picked.size === deletable.length} onChange={(e) => setPicked(e.target.checked ? new Set(deletable.map((r) => r.id)) : new Set())} />All you can delete ({deletable.length})</label>
          <button type="button" className="btn btn-outline btn-sm" disabled={!picked.size} onClick={() => remove(runs.filter((r) => picked.has(r.id)))}><Trash2 aria-hidden="true" />Delete {picked.size || ""}</button>
        </div>
      )}
      <ul className="tbx-runs">
        {runs.map((r) => {
          const isOpen = openId === r.id;
          return (
            <li key={r.id} className={`tbx-run is-${r.status}`}>
              <div className="tbx-run-row">
                {selecting && <input type="checkbox" aria-label={`Select ${r.name}`} disabled={!r.can_delete} checked={picked.has(r.id)}
                  onChange={(e) => setPicked((s) => { const n = new Set(s); e.target.checked ? n.add(r.id) : n.delete(r.id); return n; })} />}
                <StatusIcon status={r.status} />
                <button type="button" className="tbx-run-main" aria-expanded={isOpen} onClick={() => setOpenId(isOpen ? null : r.id)}>
                  <strong>{r.name}</strong>
                  <span>{r.tool_title} · #{r.id} · {when(r.created)}{r.size_bytes ? ` · ${fmtBytes(r.size_bytes)}` : ""}</span>
                </button>
                {r.status === "done" && r.outputs.filter((o) => o.kind === "vector" || o.kind === "raster").map((o) => {
                  const id = `${r.id}:${o.name}`;
                  const on = shownIds.has(id);
                  return (
                    <button key={o.name} type="button" className="icon-btn icon-btn-xs" aria-pressed={on}
                      title={`${on ? "Hide" : "Show"} ${o.title} on the map`} aria-label={`${on ? "Hide" : "Show"} ${o.title} on the map`}
                      onClick={() => (on ? onHide(id) : onShow(layerOf(r, o)))}>{on ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}</button>
                  );
                })}
              </div>
              {r.status === "failed" && <p className="tbx-error">{r.error}</p>}
              {isOpen && <RunDetail run={r} onRename={() => rename(r)} onDelete={() => remove([r])} />}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

function StatusIcon({ status }: { status: ToolRunT["status"] }) {
  if (status === "done") return <CircleCheck className="ri ri-done" aria-label="Done" />;
  if (status === "failed") return <CircleAlert className="ri ri-failed" aria-label="Failed" />;
  if (status === "running") return <LoaderCircle className="ri ri-running" aria-label="Running" />;
  return <Clock className="ri" aria-label="Queued" />;
}

function RunDetail({ run, onRename, onDelete }: { run: ToolRunT; onRename: () => void; onDelete: () => void }) {
  const detail = useQuery({ queryKey: ["tb-run", run.id, run.status], queryFn: () => api<{ run: ToolRunT }>(`/api/toolbox/runs/${run.id}/`).then((r) => r.run) });
  const [log, setLog] = useState(false);
  const d = detail.data;
  return (
    <div className="tbx-detail">
      <p className="muted small">By {run.created_by || "—"} · {run.engine}</p>
      {run.outputs.map((o) => (
        <div key={o.name} className="tbx-out">
          <div className="tbx-out-head">
            <strong>{o.title}</strong>
            <span className="muted small">
              {o.kind === "vector" && `${o.features ?? 0} ${o.geometry ?? ""} feature${o.features === 1 ? "" : "s"}`}
              {o.kind === "raster" && o.stats && `min ${fmt(o.stats.min)} · mean ${fmt(o.stats.mean)} · max ${fmt(o.stats.max)}${o.resolution_m ? ` · ${o.resolution_m} m` : ""}`}
              {o.kind === "table" && `${o.row_count ?? 0} rows`}
            </span>
          </div>
          <div className="tbx-downloads">
            <a className="pw-link" href={`${toolFileUrl(run.id, o.file)}?download=1`}><Download aria-hidden="true" />{o.kind === "vector" ? "GeoPackage" : o.kind === "raster" ? "GeoTIFF" : o.kind === "table" ? "CSV" : "File"}</a>
            {o.kind === "vector" && o.geojson && <a className="pw-link" href={`${toolFileUrl(run.id, o.geojson)}?download=1`}><Download aria-hidden="true" />GeoJSON</a>}
          </div>
          {o.kind === "table" && o.columns && o.rows && o.rows.length > 0 && (
            <div className="tbx-table"><table>
              <thead><tr>{o.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
              <tbody>{o.rows.slice(0, 20).map((row, i) => <tr key={i}>{row.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody>
            </table>{(o.row_count ?? 0) > 20 && <p className="muted small">First 20 of {o.row_count} rows; download the CSV for all.</p>}</div>
          )}
        </div>
      ))}
      {d?.report && (
        <dl className="tbx-report">{Object.entries(d.report).map(([k, v]) => <div key={k}><dt>{k}</dt><dd>{typeof v === "number" ? fmt(v) : String(v)}</dd></div>)}</dl>
      )}
      <div className="tbx-detail-actions">
        {run.can_delete && <button type="button" className="link-btn small" onClick={onRename}><Pencil aria-hidden="true" />Rename</button>}
        {d?.log && <button type="button" className="link-btn small" onClick={() => setLog((v) => !v)}>{log ? "Hide" : "Show"} log</button>}
        {run.can_delete && <button type="button" className="link-btn small tbx-danger" onClick={onDelete}><Trash2 aria-hidden="true" />Delete</button>}
      </div>
      {log && d?.log && <pre className="run-log">{d.log}</pre>}
    </div>
  );
}

/* ------------------------------------------------------------------ files */
function Files({ code, canRun, uploads }: { code: string; canRun: boolean; uploads?: Upload[] }) {
  const toast = useToast();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);

  async function add(f: File) {
    const form = new FormData();
    form.append("file", f);
    setBusy(true);
    try {
      await upload(`/api/toolbox/${code}/uploads/`, form);
      toast(`${f.name} added.`, "success");
      qc.invalidateQueries({ queryKey: ["tb-uploads", code] });
      qc.invalidateQueries({ queryKey: ["tb-inputs", code] });
    } catch (e) { toast(e instanceof ApiError ? e.message : "Couldn't upload.", "error"); }
    finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  async function remove(u: Upload) {
    if (!(await confirm({ title: `Delete "${u.name}"?`, message: "Results made from it are kept. This can't be undone.", confirmLabel: "Delete", tone: "danger" }))) return;
    try {
      await api(`/api/toolbox/uploads/${u.id}/`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["tb-uploads", code] });
      qc.invalidateQueries({ queryKey: ["tb-inputs", code] });
    } catch (e) { toast(e instanceof ApiError ? e.message : "Couldn't delete.", "error"); }
  }
  return (
    <div className="tbx-files">
      <p className="muted small">Files you add here can be used as tool inputs: GeoJSON, GeoPackage, KML/KMZ, zipped shapefile, GeoTIFF or CSV (up to 200 MB). They are kept with the project.</p>
      {canRun && (
        <label className="btn btn-outline tbx-upload">
          {busy ? <LoaderCircle className="spin" aria-hidden="true" /> : <FileUp aria-hidden="true" />}{busy ? "Uploading…" : "Add a file"}
          <input ref={input} type="file" hidden accept=".geojson,.json,.gpkg,.kml,.kmz,.zip,.fgb,.gml,.gpx,.parquet,.tif,.tiff,.csv,.tsv,.txt"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) add(f); }} />
        </label>
      )}
      {!uploads?.length ? <p className="muted small">No files yet.</p> : (
        <ul className="tbx-runs">{uploads.map((u) => (
          <li key={u.id} className="tbx-run">
            <div className="tbx-run-row">
              <span className="tbx-kind">{u.kind}</span>
              <div className="tbx-run-main"><strong>{u.name}</strong><span>{fmtBytes(u.size_bytes)} · {when(u.created)} · {u.created_by}</span></div>
              {u.can_delete && <button type="button" className="icon-btn icon-btn-xs" aria-label={`Delete ${u.name}`} title="Delete" onClick={() => remove(u)}><X aria-hidden="true" /></button>}
            </div>
          </li>
        ))}</ul>
      )}
    </div>
  );
}
