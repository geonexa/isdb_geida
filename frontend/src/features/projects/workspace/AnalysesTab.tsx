import "@/shared/styles/catalog.css";

import { useQueryClient } from "@tanstack/react-query";
import { Activity, Boxes, Building2, ChevronDown, ChevronLeft, CircleAlert, CloudLightning, Droplets, FlaskConical, Layers as LayersIcon, Mountain, Play, Search, Sparkles, Sprout, Target, Trash2, Users, type LucideIcon } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "@/shared/api/client";
import { useConfirm } from "@/shared/components/Confirm";
import { useToast } from "@/shared/components/Toasts";
import type { Evidence, Meta, ModuleCategory, ModuleInfo, PlannedAnalysis, PointPicker, Project, Run } from "@/features/projects/types";
import { ACTIVE, useModules, useRun, useRuns } from "@/features/projects/workspace/data";
import { RunForm, RunIcon, RunResult, type TableOut } from "@/features/projects/workspace/RunParts";

const MAX_TAGS = 3;
/** What an analysis does for a Core Result Indicator (manifest cri[].role). */
const CRI_ROLE: Record<string, string> = {
  measure: "measures", estimate: "gives an estimate for", verify: "helps verify",
  context: "gives context for", recorded: "records",
};
/** Indicator name shortened for a chip: "Houses/Shelters Built, Upgraded or Rehabilitated" -> "Houses/Shelters". */
const shortCri = (name: string) => {
  const head = name.split(/ (Built|Constructed|Rehabilitated|Upgraded|Installed|Provided|Supported|Benefiting|with|that|from)\b/)[0];
  return head.length > 32 ? `${head.slice(0, 30).trimEnd()}…` : head;
};

const AVAIL = { ready: "Ready", needs_data: "Needs data", not_available: "Not available" } as const;
/** Icons for the `icon` names in backend/modules/categories.yaml. */
const CATEGORY_ICONS: Record<string, LucideIcon> = {
  mountain: Mountain, droplets: Droplets, sprout: Sprout, "cloud-lightning": CloudLightning, users: Users,
  building: Building2, target: Target, activity: Activity,
};

export type AnalysesView = "modules" | "data";

type Props = {
  project: Project; meta?: Meta;
  phase: string; setPhase: (p: string) => void;
  query: string; setQuery: (q: string) => void;
  runId: number | null; openRun: (id: number | null) => void;
  onReview: (e: Evidence, a: "accept" | "reject") => void;
  onOpenTable: (t: TableOut) => void;
  /** Analysis modules, or the data layers (Data Catalog rasters cut to the area). */
  view: AnalysesView; setView: (v: AnalysesView) => void;
  dataCount: number; dataLayers: ReactNode;
  /** Point parameters (e.g. a catchment outlet) are picked on the project map. */
  picker?: PointPicker;
};

/**
 * Analyses: analysis modules (search, recommended first, grouped by category, runs, a run
 * drill-in) and data layers (open rasters by theme, cut to the area), switched at the top.
 * (The processing toolbox has its own tab: features/toolbox.)
 */
export function AnalysesTab(props: Props) {
  const { project, meta, phase, setPhase, runId, openRun } = props;
  const mods = useModules(project.code);
  const runs = useRuns(project.code);
  const run = useRun(runId);
  const canRun = project.permissions.can_edit || project.permissions.can_review;
  const canReview = canRun;
  const deleteRuns = useDeleteRuns(project.code);

  if (runId != null) {
    return (
      <div className="pw-drill">
        <button type="button" className="pw-back" onClick={() => openRun(null)}><ChevronLeft aria-hidden="true" />All analyses</button>
        {!run.data ? <p className="muted">{run.isError ? "Run not found." : "Loading…"}</p> : (
          <>
            <div className="pw-drill-head">
              <RunIcon status={run.data.status} />
              <h3>{run.data.module_title}</h3>
              {run.data.can_delete && (
                <button type="button" className="icon-btn" aria-label="Delete this run" title="Delete this run"
                  onClick={async () => { if (await deleteRuns([run.data!], run.data!.size_bytes)) openRun(null); }}><Trash2 aria-hidden="true" /></button>
              )}
            </div>
            <RunResult run={run.data} meta={meta} canReview={canReview} onReview={props.onReview} onOpenTable={props.onOpenTable} />
          </>
        )}
      </div>
    );
  }

  const phases = mods.data?.phases ?? [];
  const switcher = (
    <div className="pw-views" role="tablist" aria-label="Analyses or data layers">
      <button type="button" role="tab" aria-selected={props.view === "modules"} onClick={() => props.setView("modules")}>
        <FlaskConical aria-hidden="true" />Analysis modules
      </button>
      <button type="button" role="tab" aria-selected={props.view === "data"} onClick={() => props.setView("data")}>
        <LayersIcon aria-hidden="true" />Data layers{props.dataCount > 0 && <em>{props.dataCount}</em>}
      </button>
    </div>
  );
  // Phase first: each phase has its own analyses and data layers (a layer may serve several phases).
  const phasePicker = (
    <div className="pw-seg" role="tablist" aria-label="Project phase">
      {phases.map((p) => (
        <button key={p.value} role="tab" aria-selected={phase === p.value} onClick={() => setPhase(p.value)}>
          {p.label}<span>{p.instrument}</span>
        </button>
      ))}
    </div>
  );
  return (
    <div className="pw-analyses">
      {phasePicker}
      {switcher}
      {props.view === "data" && props.dataLayers}
      {props.view === "modules" && (
        <>
          {mods.isPending && <p className="muted">Loading modules…</p>}
          {mods.isError && <p className="field-error"><CircleAlert aria-hidden="true" />{(mods.error as Error).message}</p>}
          {mods.data && <Catalogue {...props} modules={mods.data.modules} planned={mods.data.planned ?? []} categories={mods.data.categories ?? []} canRun={canRun} />}
          <RunsList runs={(runs.data ?? []).filter((r) => r.phase === phase)} onOpen={openRun} onDelete={deleteRuns} />
        </>
      )}
    </div>
  );
}

function Catalogue({ project, phase, query, setQuery, openRun, modules, planned, categories, canRun, picker }: Props & { modules: ModuleInfo[]; planned: PlannedAnalysis[]; categories: ModuleCategory[]; canRun: boolean }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [readyOnly, setReadyOnly] = useState(false);
  const [openForm, setOpenForm] = useState<string | null>(null);

  const { recommended, groups, total } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const titles = new Map(categories.map((c) => [c.id, c.title]));
    const matching = modules.filter((m) => m.phases.includes(phase))
      .filter((m) => !readyOnly || m.availability?.status === "ready")
      .filter((m) => !q || [m.title, m.question, m.description, titles.get(m.category) ?? "", ...m.themes, ...m.cri.map((c) => c.code)].join(" ").toLowerCase().includes(q));
    const list = matching;
    const isRec = (m: ModuleInfo) => (m.cri_in_project?.length ?? 0) > 0 || m.themes.some((t) => project.themes.includes(t));
    const score = (m: ModuleInfo) => (m.cri_in_project?.length ?? 0) * 10 + (isRec(m) ? 2 : 0) + (m.availability?.status === "ready" ? 1 : 0);
    // "Recommended" is its own section unless searching (then matches stay in their categories).
    const pullOut = !q;
    const recommended = pullOut ? list.filter((m) => (m.cri_in_project?.length ?? 0) > 0).sort((a, b) => score(b) - score(a)) : [];
    const rest = list.filter((m) => !recommended.includes(m)).sort((a, b) => score(b) - score(a) || a.title.localeCompare(b.title));
    const known = new Set(categories.map((c) => c.id));
    // Planned analyses for this phase (not runnable yet), listed after the built ones in each category.
    const plan = readyOnly ? [] : planned.filter((a) => a.phases.includes(phase))
      .filter((a) => !q || [a.title, a.question, titles.get(a.category) ?? ""].join(" ").toLowerCase().includes(q));
    const groups = [...categories, { id: "other", title: "Other", description: "", icon: "", order: 999, modules: 0 }]
      .map((c) => ({
        cat: c,
        mods: rest.filter((m) => (known.has(m.category) ? m.category : "other") === c.id),
        plan: plan.filter((a) => (known.has(a.category) ? a.category : "other") === c.id),
      }))
      .filter((g) => g.mods.length + g.plan.length > 0);
    return { recommended, groups, total: list.length + plan.length };
  }, [modules, planned, categories, phase, query, readyOnly, project.themes]);

  async function start(m: ModuleInfo, params: Record<string, string>) {
    try {
      const res = await api<{ run: Run }>("/api/analysis/runs/", { method: "POST", body: { project: project.code, module: m.id, phase, params } });
      toast(`${m.title} queued.`, "success");
      setOpenForm(null);
      qc.invalidateQueries({ queryKey: ["runs", project.code] });
      openRun(res.run.id);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't start the analysis.", "error");
    }
  }

  const row = (m: ModuleInfo) => (
    <ModuleRow key={m.id} m={m} canRun={canRun} formOpen={openForm === m.id} picker={picker}
      onRun={() => setOpenForm(m.id)} onCancel={() => setOpenForm(null)} onStart={(p) => start(m, p)} />
  );

  return (
    <>
      <div className="pw-filter">
        <label className="psearch"><Search aria-hidden="true" /><input type="search" placeholder="Search modules, themes, CRI…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search modules" /></label>
        <label className="pw-check"><input type="checkbox" checked={readyOnly} onChange={(e) => setReadyOnly(e.target.checked)} />Ready only</label>
      </div>
      {total === 0 && <p className="muted small">No analyses match{query ? ` “${query}”` : ""} in this phase.</p>}
      <div className="pw-acc">
        {recommended.length > 0 && (
          <Accordion icon={Sparkles} title="Recommended for this project" count={recommended.length} open>
            <ul className="pw-mods">{recommended.map(row)}</ul>
          </Accordion>
        )}
        {groups.map(({ cat, mods, plan }) => (
          // Collapsed by default; a search opens every category with matches.
          <Accordion key={cat.id} icon={CATEGORY_ICONS[cat.icon] ?? Boxes} title={cat.title} count={mods.length + plan.length} open={!!query.trim()}
            ready={mods.length ? mods.filter((m) => m.availability?.status === "ready").length : undefined}>
            {cat.description && <p className="pw-cat-desc">{cat.description}</p>}
            {mods.length > 0 && <ul className="pw-mods">{mods.map(row)}</ul>}
            {plan.length > 0 && (
              <ul className="pw-mods pw-planned">
                {plan.map((a) => (
                  <li key={a.id} className="pw-mod is-planned">
                    <div className="pw-mod-main">
                      <div className="pw-mod-text"><strong>{a.title}</strong><p>{a.question}</p></div>
                      <span className="avail avail-planned">Planned</span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </Accordion>
        ))}
      </div>
    </>
  );
}

/** A collapsible group of modules (same look as the Data layers sections). */
function Accordion({ icon: Icon, title, count, ready, open, children }: {
  icon: LucideIcon; title: string; count: number; ready?: number; open?: boolean; children: ReactNode;
}) {
  return (
    <details className="gp-group pw-acc-group" open={open || undefined}>
      <summary>
        <span className="gp-group-type"><Icon aria-hidden="true" /></span>
        <span className="gp-group-name">{title}</span>
        {ready != null && ready < count && <span className="pw-acc-ready" title="Modules ready to run with the data available">{ready} ready</span>}
        <span className="gp-group-n">{count}</span>
        <ChevronDown className="gp-chev" aria-hidden="true" />
      </summary>
      <div className="pw-acc-body">{children}</div>
    </details>
  );
}

function ModuleRow({ m, canRun, formOpen, picker, onRun, onCancel, onStart }: {
  m: ModuleInfo; canRun: boolean; formOpen: boolean; picker?: PointPicker; onRun: () => void; onCancel: () => void; onStart: (p: Record<string, string>) => void;
}) {
  const av = m.availability ?? { status: "not_available" as const, reasons: [] };
  const data = m.inputs.filter((i) => i.dataset);
  return (
    <li className={`pw-mod is-${av.status}`}>
      <div className="pw-mod-main">
        <div className="pw-mod-text">
          <strong>{m.title}</strong>
          <p>{m.question}</p>
        </div>
        {canRun && av.status === "ready" && !formOpen
          ? <button type="button" className="btn btn-outline btn-sm" onClick={onRun}><Play aria-hidden="true" />Run</button>
          : <span className={`avail avail-${av.status}`}>{AVAIL[av.status]}</span>}
      </div>
      <div className="mod-tags">
        {m.cri.map((c) => {
          const hit = m.cri_in_project?.includes(c.code);
          const tip = [`IsDB Core Result Indicator ${c.code}${c.name ? `: ${c.name}` : ""}${c.unit ? ` (${c.unit})` : ""}`,
            `This analysis ${CRI_ROLE[c.role] ?? "relates to"} it.`, hit ? "It is in this project's Results Framework." : ""].filter(Boolean).join("\n");
          return <span key={c.code} className={`cri-tag${hit ? " is-match" : ""}`} title={tip}>CRI {c.code}{c.name ? ` · ${shortCri(c.name)}` : ""}</span>;
        })}
        {data.slice(0, MAX_TAGS).map((i) => <span key={i.name} className="ds-tag" title={i.dataset!.citation}>{i.dataset!.title}</span>)}
        {data.length > MAX_TAGS && <span className="ds-tag" title={data.slice(MAX_TAGS).map((i) => i.dataset!.title).join("\n")}>+{data.length - MAX_TAGS} more layers</span>}
      </div>
      {av.reasons.length > 0 && <ul className="mod-reasons">{av.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      {formOpen && <RunForm module={m} picker={picker} onCancel={onCancel} onStart={onStart} />}
    </li>
  );
}

const RUNS_SHOWN = 5;
const RUN_FILTERS = [
  { id: "all", label: "All", match: () => true },
  { id: "done", label: "Done", match: (r: Run) => r.status === "done" },
  { id: "active", label: "Running", match: (r: Run) => ACTIVE.has(r.status) },
  { id: "failed", label: "Failed", match: (r: Run) => r.status === "failed" || r.status === "cancelled" },
] as const;

/**
 * Runs in the current phase, newest first: compact one-line rows, the latest few shown with
 * "Show all", and status filters once there are more than a handful.
 */
const fmtBytes = (b: number) => b >= 1e9 ? `${(b / 1e9).toFixed(1)} GB` : b >= 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} kB`;

/** Delete runs after a confirmation; resolves true when at least one was deleted. */
function useDeleteRuns(code: string) {
  const confirm = useConfirm();
  const toast = useToast();
  const qc = useQueryClient();
  return async (list: Run[], bytes?: number): Promise<boolean> => {
    if (!list.length) return false;
    const one = list.length === 1;
    const ok = await confirm({
      title: one ? `Delete run #${list[0].id} (${list[0].module_title})?` : `Delete ${list.length} runs?`,
      message: `${one ? "Its" : "Their"} results, map layers and downloads${bytes ? ` (${fmtBytes(bytes)})` : ""} are removed, with any proposed or rejected evidence. Runs with accepted evidence are kept. The project's Activity log records the deletion. This can't be undone.`,
      confirmLabel: one ? "Delete run" : `Delete ${list.length} runs`, tone: "danger",
    });
    if (!ok) return false;
    try {
      const res = await api<{ deleted: { id: number }[]; refused?: { id: number; reason: string }[] }>(
        one ? `/api/analysis/runs/${list[0].id}/` : "/api/analysis/runs/delete/",
        one ? { method: "DELETE" } : { method: "POST", body: { ids: list.map((r) => r.id) } });
      if (res.deleted.length) toast(res.deleted.length === 1 ? `Run #${res.deleted[0].id} deleted.` : `${res.deleted.length} runs deleted.`, "success");
      for (const r of res.refused ?? []) toast(r.reason, "error");
      qc.invalidateQueries({ queryKey: ["runs", code] });
      qc.invalidateQueries({ queryKey: ["evidence", code] });
      qc.invalidateQueries({ queryKey: ["project", code] });
      return res.deleted.length > 0;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't delete.", "error");
      return false;
    }
  };
}

function RunsList({ runs, onOpen, onDelete }: { runs: Run[]; onOpen: (id: number) => void; onDelete: (list: Run[]) => Promise<boolean> }) {
  const [filter, setFilter] = useState<(typeof RUN_FILTERS)[number]["id"]>("all");
  const [selecting, setSelecting] = useState(false);
  const [picked, setPicked] = useState<Set<number>>(new Set());
  const deletable = runs.filter((r) => r.can_delete);
  const [all, setAll] = useState(false);
  const sorted = useMemo(() => [...runs].sort((a, b) => b.created.localeCompare(a.created)), [runs]);
  const counts = Object.fromEntries(RUN_FILTERS.map((f) => [f.id, sorted.filter(f.match).length]));
  const current = RUN_FILTERS.find((f) => f.id === filter)!;
  const list = sorted.filter(current.match);
  const shown = all ? list : list.slice(0, RUNS_SHOWN);
  const date = (iso: string) => new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short" });

  return (
    <section className="pw-group pw-runs">
      <h4 className="pw-h4">Runs in this phase <span className="muted">{runs.length}</span>
        {deletable.length > 0 && (
          <button type="button" className="link-btn small pw-runs-select" onClick={() => { setSelecting((v) => !v); setPicked(new Set()); }}>
            {selecting ? "Done" : "Select"}
          </button>
        )}
      </h4>
      {selecting && (
        <div className="pw-runs-bulk">
          <label><input type="checkbox" checked={picked.size > 0 && picked.size === deletable.length}
            onChange={(e) => setPicked(e.target.checked ? new Set(deletable.map((r) => r.id)) : new Set())} />All you can delete ({deletable.length})</label>
          <button type="button" className="btn btn-outline btn-sm" disabled={!picked.size}
            onClick={async () => { if (await onDelete(runs.filter((r) => picked.has(r.id)))) { setPicked(new Set()); setSelecting(false); } }}>
            <Trash2 aria-hidden="true" />Delete {picked.size || ""}
          </button>
        </div>
      )}
      {runs.length === 0 ? <p className="muted small">No runs yet. Run a module above; results open here and on the map.</p> : (
        <>
          {runs.length > RUNS_SHOWN && (
            <div className="pw-run-filters" role="group" aria-label="Filter runs by status">
              {RUN_FILTERS.map((f) => (
                <button key={f.id} type="button" aria-pressed={filter === f.id} disabled={!counts[f.id] && f.id !== "all"}
                  onClick={() => { setFilter(f.id); setAll(false); }}>
                  {f.label}<span>{counts[f.id]}</span>
                </button>
              ))}
            </div>
          )}
          <ul className="run-list">
            {shown.map((r) => (
              <li key={r.id} className={selecting ? "is-selecting" : undefined}>
                {selecting && (
                  <input type="checkbox" aria-label={`Select run #${r.id}`} disabled={!r.can_delete} checked={picked.has(r.id)}
                    title={r.can_delete ? undefined : "You can't delete this run (not yours, still running, or it has accepted evidence)."}
                    onChange={(e) => setPicked((s) => { const n = new Set(s); e.target.checked ? n.add(r.id) : n.delete(r.id); return n; })} />
                )}
                <button type="button" className={`run-row is-${r.status}`} onClick={() => onOpen(r.id)}
                  title={`${r.module_title} · run #${r.id} · ${new Date(r.created).toLocaleString()} · ${r.created_by}`}>
                  <RunIcon status={r.status} />
                  <span className="run-title">{r.module_title}</span>
                  <span className="run-meta">{ACTIVE.has(r.status) ? `${r.progress}%` : `#${r.id} · ${date(r.created)}`}</span>
                  {ACTIVE.has(r.status) && <i className="run-row-bar" style={{ width: `${r.progress}%` }} aria-hidden="true" />}
                </button>
              </li>
            ))}
          </ul>
          {list.length === 0 && <p className="muted small">No runs with this status.</p>}
          {list.length > RUNS_SHOWN && (
            <button type="button" className="link-btn small pw-runs-more" onClick={() => setAll((v) => !v)}>
              {all ? "Show fewer" : `Show all ${list.length} runs`}
            </button>
          )}
        </>
      )}
    </section>
  );
}
