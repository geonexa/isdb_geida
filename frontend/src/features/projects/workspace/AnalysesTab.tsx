import { useQueryClient } from "@tanstack/react-query";
import { Boxes, Building2, ChevronLeft, CircleAlert, FlaskConical, Layers as LayersIcon, Map as MapIcon, Network, Play, Route, School, Search, Sparkles, type LucideIcon } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { api, ApiError } from "@/shared/api/client";
import { useToast } from "@/shared/components/Toasts";
import type { Evidence, Meta, ModuleCategory, ModuleInfo, Project, Run } from "@/features/projects/types";
import { ACTIVE, useModules, useRun, useRuns } from "@/features/projects/workspace/data";
import { RunForm, RunIcon, RunResult, type TableOut } from "@/features/projects/workspace/RunParts";

const MAX_TAGS = 3;
const AVAIL = { ready: "Ready", needs_data: "Needs data", not_available: "Not available" } as const;
/** Icons for the `icon` names in backend/modules/categories.yaml. */
const CATEGORY_ICONS: Record<string, LucideIcon> = { map: MapIcon, school: School, route: Route, building: Building2, network: Network };

type Props = {
  project: Project; meta?: Meta;
  phase: string; setPhase: (p: string) => void;
  query: string; setQuery: (q: string) => void;
  runId: number | null; openRun: (id: number | null) => void;
  onReview: (e: Evidence, a: "accept" | "reject") => void;
  onOpenTable: (t: TableOut) => void;
  /** Analysis modules, or the data layers (Data Catalog rasters cut to the area). */
  view: "modules" | "data"; setView: (v: "modules" | "data") => void;
  dataCount: number; dataLayers: ReactNode;
};

/**
 * Analyses: analysis modules (search, recommended first, grouped by category, runs, a run
 * drill-in) and data layers (open rasters by theme, cut to the area), switched at the top.
 */
export function AnalysesTab(props: Props) {
  const { project, meta, phase, setPhase, runId, openRun } = props;
  const mods = useModules(project.code);
  const runs = useRuns(project.code);
  const run = useRun(runId);
  const canRun = project.permissions.can_edit || project.permissions.can_review;
  const canReview = canRun;

  if (runId != null) {
    return (
      <div className="pw-drill">
        <button type="button" className="pw-back" onClick={() => openRun(null)}><ChevronLeft aria-hidden="true" />All analyses</button>
        {!run.data ? <p className="muted">{run.isError ? "Run not found." : "Loading…"}</p> : (
          <>
            <div className="pw-drill-head">
              <RunIcon status={run.data.status} />
              <h3>{run.data.module_title}</h3>
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
  if (props.view === "data") return <div className="pw-analyses">{phasePicker}{switcher}{props.dataLayers}</div>;
  return (
    <div className="pw-analyses">
      {phasePicker}
      {switcher}
      {mods.isPending && <p className="muted">Loading modules…</p>}
      {mods.isError && <p className="field-error"><CircleAlert aria-hidden="true" />{(mods.error as Error).message}</p>}
      {mods.data && <Catalogue {...props} modules={mods.data.modules} categories={mods.data.categories ?? []} canRun={canRun} />}
      <RunsList runs={(runs.data ?? []).filter((r) => r.phase === phase)} onOpen={openRun} />
    </div>
  );
}

function Catalogue({ project, phase, query, setQuery, openRun, modules, categories, canRun }: Props & { modules: ModuleInfo[]; categories: ModuleCategory[]; canRun: boolean }) {
  const toast = useToast();
  const qc = useQueryClient();
  const [readyOnly, setReadyOnly] = useState(false);
  const [category, setCategory] = useState<string>("all");
  const [openForm, setOpenForm] = useState<string | null>(null);

  const { recommended, groups, total, counts } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const titles = new Map(categories.map((c) => [c.id, c.title]));
    const matching = modules.filter((m) => m.phases.includes(phase))
      .filter((m) => !readyOnly || m.availability?.status === "ready")
      .filter((m) => !q || [m.title, m.question, m.description, titles.get(m.category) ?? "", ...m.themes, ...m.cri.map((c) => c.code)].join(" ").toLowerCase().includes(q));
    const counts = new Map<string, number>();
    for (const m of matching) counts.set(m.category, (counts.get(m.category) ?? 0) + 1);
    const list = matching.filter((m) => category === "all" || m.category === category);
    const isRec = (m: ModuleInfo) => (m.cri_in_project?.length ?? 0) > 0 || m.themes.some((t) => project.themes.includes(t));
    const score = (m: ModuleInfo) => (m.cri_in_project?.length ?? 0) * 10 + (isRec(m) ? 2 : 0) + (m.availability?.status === "ready" ? 1 : 0);
    // "Recommended" is its own section only in the full catalogue; inside one category, recommended modules come first.
    const pullOut = category === "all" && !q;
    const recommended = pullOut ? list.filter((m) => (m.cri_in_project?.length ?? 0) > 0).sort((a, b) => score(b) - score(a)) : [];
    const rest = list.filter((m) => !recommended.includes(m)).sort((a, b) => score(b) - score(a) || a.title.localeCompare(b.title));
    const known = new Set(categories.map((c) => c.id));
    const groups = [...categories, { id: "other", title: "Other", description: "", icon: "", order: 999, modules: 0 }]
      .map((c) => ({ cat: c, mods: rest.filter((m) => (known.has(m.category) ? m.category : "other") === c.id) }))
      .filter((g) => g.mods.length > 0);
    return { recommended, groups, total: list.length, counts: { all: matching.length, by: counts } };
  }, [modules, categories, phase, query, readyOnly, category, project.themes]);

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
    <ModuleRow key={m.id} m={m} canRun={canRun} formOpen={openForm === m.id}
      onRun={() => setOpenForm(m.id)} onCancel={() => setOpenForm(null)} onStart={(p) => start(m, p)} />
  );

  return (
    <>
      <div className="pw-filter">
        <label className="psearch"><Search aria-hidden="true" /><input type="search" placeholder="Search modules, themes, CRI…" value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search modules" /></label>
        <label className="pw-check"><input type="checkbox" checked={readyOnly} onChange={(e) => setReadyOnly(e.target.checked)} />Ready only</label>
      </div>
      {categories.length > 0 && (
        <div className="pw-cats" role="group" aria-label="Category">
          <button type="button" className="pw-cat" aria-pressed={category === "all"} onClick={() => setCategory("all")}>
            <Boxes aria-hidden="true" />All<span>{counts.all}</span>
          </button>
          {categories.map((c) => {
            const Icon = CATEGORY_ICONS[c.icon] ?? Boxes;
            const n = counts.by.get(c.id) ?? 0;
            return (
              <button key={c.id} type="button" className="pw-cat" aria-pressed={category === c.id} disabled={n === 0 && category !== c.id}
                title={c.description} onClick={() => setCategory(category === c.id ? "all" : c.id)}>
                <Icon aria-hidden="true" />{c.title}<span>{n}</span>
              </button>
            );
          })}
        </div>
      )}
      {total === 0 && <p className="muted small">No modules match{query ? ` “${query}”` : ""}{category !== "all" ? " in this category" : ""} in this phase.</p>}
      {recommended.length > 0 && (
        <section className="pw-group">
          <h4 className="pw-h4"><Sparkles aria-hidden="true" />Recommended for this project <span className="muted">{recommended.length}</span></h4>
          <ul className="pw-mods">{recommended.map(row)}</ul>
        </section>
      )}
      {groups.map(({ cat, mods }) => {
        const Icon = CATEGORY_ICONS[cat.icon] ?? Boxes;
        return (
          <section key={cat.id} className="pw-group">
            <h4 className="pw-h4"><Icon aria-hidden="true" />{cat.title} <span className="muted">{mods.length}</span></h4>
            {cat.description && <p className="pw-cat-desc">{cat.description}</p>}
            <ul className="pw-mods">{mods.map(row)}</ul>
          </section>
        );
      })}
    </>
  );
}

function ModuleRow({ m, canRun, formOpen, onRun, onCancel, onStart }: {
  m: ModuleInfo; canRun: boolean; formOpen: boolean; onRun: () => void; onCancel: () => void; onStart: (p: Record<string, string>) => void;
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
          return <span key={c.code} className={`cri-tag${hit ? " is-match" : ""}`} title={hit ? "In this project's Results Framework" : c.role}>CRI {c.code}</span>;
        })}
        {data.slice(0, MAX_TAGS).map((i) => <span key={i.name} className="ds-tag" title={i.dataset!.citation}>{i.dataset!.title}</span>)}
        {data.length > MAX_TAGS && <span className="ds-tag" title={data.slice(MAX_TAGS).map((i) => i.dataset!.title).join("\n")}>+{data.length - MAX_TAGS} more layers</span>}
      </div>
      {av.reasons.length > 0 && <ul className="mod-reasons">{av.reasons.map((r) => <li key={r}>{r}</li>)}</ul>}
      {formOpen && <RunForm module={m} onCancel={onCancel} onStart={onStart} />}
    </li>
  );
}

function RunsList({ runs, onOpen }: { runs: Run[]; onOpen: (id: number) => void }) {
  return (
    <section className="pw-group">
      <h4 className="pw-h4">Runs in this phase <span className="muted">{runs.length}</span></h4>
      {runs.length === 0 ? <p className="muted small">No runs yet. Run a module above; results open here and on the map.</p> : (
        <ul className="run-list">
          {runs.map((r) => (
            <li key={r.id}>
              <button type="button" className="run-row" onClick={() => onOpen(r.id)}>
                <RunIcon status={r.status} />
                <span><strong>{r.module_title}</strong><span className="muted small">#{r.id} · {new Date(r.created).toLocaleDateString()} · {r.created_by}</span></span>
                {ACTIVE.has(r.status) && <span className="small">{r.progress}%</span>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
