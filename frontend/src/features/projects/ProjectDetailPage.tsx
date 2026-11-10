import type * as maplibregl from "maplibre-gl";
import { BadgeCheck, CheckCircle2, ChevronLeft, FileText, FlaskConical, History, LayoutDashboard, Pencil, Send, Target, Trash2, Undo2 } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { api, ApiError } from "@/shared/api/client";
import { useAuth } from "@/features/auth/AuthContext";
import type { PrintContext } from "@/features/print/layout";
import { useConfirm } from "@/shared/components/Confirm";
import { useToast } from "@/shared/components/Toasts";
import { useBodyClass, useTitle } from "@/shared/lib/dom";
import { applyVectorOverride, loadStyles, saveStyles, type LayerStyles } from "@/features/projects/layerStyle";
import { legendSwatches } from "@/features/projects/vectorStyle";
import { label, StatusChip, useMeta, useProject, useSetProject } from "@/features/projects/data";
import { ProjectMap } from "@/features/projects/ProjectMap";
import type { Evidence, Project, RunOutput } from "@/features/projects/types";
import { AnalysesTab } from "@/features/projects/workspace/AnalysesTab";
import { ACTIVE, fileUrl, STAGE_PHASE, useEvidence, useReviewEvidence, useRun, useRuns } from "@/features/projects/workspace/data";
import { LayerPanel, TableDrawer } from "@/features/projects/workspace/MapOverlays";
import { DataLayers, effectiveLegend, isVectorTiles, legendNumber, useSatelliteLayers, useSatelliteTiles, type SatState } from "@/features/projects/workspace/satellite";
import type { TableOut } from "@/features/projects/workspace/RunParts";
import { ActivityTab, DocumentsTab, EvidenceTab, OverviewTab, ResultsTab } from "@/features/projects/workspace/Tabs";

// The export composer (and GeoLibre's print engine behind it) loads on first use.
const PrintDialog = lazy(() => import("@/features/print/PrintDialog"));

const TABS = [
  { id: "overview", label: "Overview", icon: LayoutDashboard },
  { id: "results", label: "Results", icon: Target },
  { id: "analyses", label: "Analyses", icon: FlaskConical },
  { id: "evidence", label: "Evidence", icon: BadgeCheck },
  { id: "documents", label: "Documents", icon: FileText },
  { id: "activity", label: "Activity", icon: History },
] as const;
type TabId = (typeof TABS)[number]["id"];

/**
 * Project workspace: header, icon rail, one side panel, and a single persistent map.
 * Tabs and the open run live in the URL (?tab=analyses&phase=…&run=12) so views can be shared.
 */
export default function ProjectDetailPage() {
  const { code = "" } = useParams();
  const meta = useMeta();
  const q = useProject(code);
  const [params, setParams] = useSearchParams();
  useBodyClass("page-project");
  useTitle(code);

  const setParam = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(patch)) (v == null || v === "" ? next.delete(k) : next.set(k, v));
    setParams(next, { replace: true });
  };

  if (q.isPending) return <div className="pw-loading muted">Loading…</div>;
  if (q.isError || !q.data) {
    return <div className="section"><div className="wrap"><h1>Project not found</h1><p className="muted">It may be a draft you can't see.</p><Link className="text-link" to="/projects">Back to projects</Link></div></div>;
  }
  return <Workspace p={q.data} params={params} setParam={setParam} meta={meta.data} />;
}

function Workspace({ p, params, setParam, meta }: {
  p: Project; params: URLSearchParams; setParam: (patch: Record<string, string | null>) => void; meta: ReturnType<typeof useMeta>["data"];
}) {
  const toast = useToast();
  const runs = useRuns(p.code);
  const evidence = useEvidence(p.code);
  const reviewEv = useReviewEvidence(p.code);

  // The old Data catalog tab now lives in Analyses (?tab=analyses&view=data).
  const tabParam = params.get("tab") === "satellite" ? "analyses" : params.get("tab");
  const tab = (TABS.some((t) => t.id === tabParam) ? tabParam : "overview") as TabId;
  const view = params.get("tab") === "satellite" || params.get("view") === "data" ? "data" : "modules";
  const phase = params.get("phase") ?? STAGE_PHASE[p.stage] ?? "preparation";
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const run = useRun(runId).data;

  const [showArea, setShowArea] = useState(true);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [table, setTable] = useState<TableOut | null>(null);
  const [mapRef, setMapRef] = useState<maplibregl.Map | null>(null);
  const [printing, setPrinting] = useState(false);
  const [sat, setSat] = useState<SatState>({});
  const [styles, setStyles] = useState<LayerStyles>(() => loadStyles(p.code));
  useEffect(() => saveStyles(p.code, styles), [p.code, styles]);
  const satGroups = useSatelliteLayers(p.code, !!p.area).data ?? [];
  const satLayers = satGroups.flatMap((g) => g.layers);
  // Vector tile layers (PMTiles) are read by the map itself; the rest go through GEIDA's tile route.
  const vtLayers = satLayers.filter((l) => sat[l.id] && isVectorTiles(l));
  const satTiles = useSatelliteTiles(p.code, Object.fromEntries(Object.entries(sat).filter(([id]) => !vtLayers.some((l) => l.id === id))));
  const vectorTiles = vtLayers.map((l) => ({
    id: l.id, url: l.pmtiles!.url.replace(/\{year\}/g, String(sat[l.id].year ?? l.year ?? "")), def: l.pmtiles!,
    opacity: sat[l.id].opacity, threshold: sat[l.id].threshold, attribution: l.attribution,
  }));
  // MapLibre needs absolute tile URLs; GEIDA's tile route is relative to the site. (Not new URL(): it would escape {z}/{x}/{y}.)
  const rasters = satTiles.filter((t) => t.query.data).map((t) => ({
    id: t.id, tiles: t.query.data!.tiles.map((u) => (u.startsWith("/") ? window.location.origin + u : u)), opacity: t.opacity,
    attribution: t.query.data!.attribution, minzoom: t.query.data!.minzoom, maxzoom: t.query.data!.maxzoom ?? undefined,
  }));
  const satErrors = Object.fromEntries(satTiles.filter((t) => t.query.error).map((t) => [t.id, (t.query.error as Error).message]));
  // Loading = fetching the tile URL, or the map still drawing that layer's tiles.
  const [tilesLoading, setTilesLoading] = useState<Set<string>>(() => new Set());
  const satLoading = new Set([...satTiles.filter((t) => t.query.isFetching).map((t) => t.id), ...[...tilesLoading].filter((id) => sat[id])]);
  const { user } = useAuth();

  const openRun = (id: number | null) => {
    setHidden(new Set()); setTable(null);
    setParam({ run: id == null ? null : String(id), ...(id != null ? { tab: "analyses" } : {}) });
  };
  const go = (t: string) => setParam({ tab: t === "overview" ? null : t });
  const review = async (e: Evidence, a: "accept" | "reject") => {
    try { await reviewEv(e, a); } catch (err) { toast(err instanceof ApiError ? err.message : "Couldn't update the evidence.", "error"); }
  };

  // Map overlays from the open run. Rasters: the first one is on by default, the rest off.
  const outs = run?.status === "done" ? run.outputs ?? [] : [];
  const imgs = outs.filter((o): o is Extract<RunOutput, { type: "image" }> => o.type === "image");
  const vecs = outs.filter((o): o is Extract<RunOutput, { type: "vector" }> => o.type === "vector");
  const isHidden = (name: string) => hidden.has(name) !== (imgs.findIndex((o) => o.name === name) > 0);
  const toggle = (name: string) => setHidden((h) => { const n = new Set(h); n.has(name) ? n.delete(name) : n.add(name); return n; });
  const images = useMemo(() => imgs.filter((o) => !isHidden(o.name)).map((o) => ({ id: `${run!.id}-${o.name}`, url: fileUrl(run!.id, o.file), bounds: o.bounds, opacity: styles.images[o.name]?.opacity })), [run, hidden, styles.images]);
  const vectors = useMemo(() => vecs.filter((o) => !isHidden(o.name)).map((o) => ({ id: `${run!.id}-${o.name}`, url: fileUrl(run!.id, o.file), style: applyVectorOverride(o.style, styles.vectors[o.name]), title: o.title })), [run, hidden, styles.vectors]);
  const hiddenNow = new Set([...imgs, ...vecs].map((o) => o.name).filter(isHidden));

  const proposed = (evidence.data ?? []).filter((e) => e.status === "proposed").length;
  const active = (runs.data ?? []).filter((r) => ACTIVE.has(r.status)).length;
  const badge: Partial<Record<TabId, number>> = { evidence: proposed, analyses: active || undefined, results: p.indicators.length || undefined };
  const canReview = p.permissions.can_review || p.permissions.can_edit;
  const fit = p.area?.bbox ?? meta?.countries.find((c) => c.iso3 === p.country_iso3)?.bbox ?? null;
  const current = TABS.find((t) => t.id === tab)!;

  // What the export starts from: the layers on the map now, and where their data comes from.
  // Satellite layers: the first continuous one becomes the print colour bar, the rest legend entries.
  const satOn = satLayers.filter((l) => sat[l.id] && (rasters.some((r) => r.id === l.id) || isVectorTiles(l)));
  // Legends as drawn now, with the user's palettes and ranges.
  const satLg = (id: string) => effectiveLegend(satLayers.find((l) => l.id === id)!, sat[id]);
  const rampLayer = satOn.find((l) => l.legend?.type === "ramp");
  const rampLg = rampLayer ? satLg(rampLayer.id) : undefined;
  const ramp = rampLayer && rampLg?.type === "ramp"
    ? { colors: rampLg.palette, min: legendNumber(rampLg.min), max: legendNumber(rampLg.max), label: `${rampLayer.name}${rampLg.unit && !rampLayer.name.includes(rampLg.unit) ? ` (${rampLg.unit})` : ""}${sat[rampLayer.id].year ? `, ${sat[rampLayer.id].year}` : ""}` }
    : null;
  const satLegend = satOn.filter((l) => l !== rampLayer && l.legend).map((l) => {
    const lg = satLg(l.id)!;
    return {
      id: `sat-${l.id}`,
      name: `${l.name}${sat[l.id].year ? ` (${sat[l.id].year})` : ""}`,
      swatches: lg.type === "classes"
        ? lg.items.map(([color, label]) => ({ color, label }))
        : [{ color: lg.palette[0], label: lg.min }, { color: lg.palette[lg.palette.length - 1], label: `${lg.max} ${lg.unit ?? ""}`.trim() }],
    };
  });
  const legend = [
    ...(showArea && p.area ? [{ id: "area", name: "Area of influence", swatches: [{ color: styles.area.color }] }] : []),
    ...satLegend,
    ...imgs.filter((o) => !isHidden(o.name)).map((o) => ({ id: `img-${o.name}`, name: o.title, swatches: o.legend.map((l) => ({ color: l.color, label: l.label })) })),
    ...vecs.filter((o) => !isHidden(o.name)).map((o) => ({ id: `vec-${o.name}`, name: o.title, swatches: legendSwatches(applyVectorOverride(o.style, styles.vectors[o.name])) })),
  ];
  const printContext = (): PrintContext => {
    const styleSources = Object.values(mapRef?.getStyle().sources ?? {}) as { attribution?: string }[];
    const strip = (html: string) => new DOMParser().parseFromString(html, "text/html").body.textContent ?? "";
    return {
      title: p.title,
      subtitle: [p.country_name, run?.status === "done" && (imgs.length || vecs.length) ? run.module_title : "", ...satOn.map((l) => l.name)].filter(Boolean).join(" · "),
      code: p.code,
      country: p.country_name,
      author: user?.full_name || user?.username || "",
      sources: [
        ...(p.area ? ["Area of influence: GEIDA project record"] : []),
        ...(run?.status === "done" && (imgs.length || vecs.length) ? (run.datasets ?? []).map((d) => d.citation || d.title) : []),
        ...styleSources.map((src) => strip(src.attribution ?? "")),
      ],
    };
  };

  return (
    <div className="pw">
      <div className="pw-body">
        <nav className="pw-rail" aria-label="Project sections">
          {TABS.map((t) => (
            <button key={t.id} type="button" className="pw-rail-btn" aria-current={tab === t.id ? "page" : undefined} onClick={() => go(t.id)}>
              <t.icon aria-hidden="true" />
              <span>{t.label}</span>
              {badge[t.id] ? <em className={t.id === "evidence" || t.id === "analyses" ? "is-hot" : ""}>{badge[t.id]}</em> : null}
            </button>
          ))}
        </nav>

        <aside className="pw-panel" aria-label={current.label}>
          <Header p={p} meta={meta} />
          <div className="pw-panel-body">
          {!(tab === "analyses" && runId != null) && <h2 className="pw-panel-title">{current.label}</h2>}
          {tab === "overview" && <OverviewTab p={p} meta={meta} runs={runs.data ?? []} evidence={evidence.data ?? []} go={go} />}
          {tab === "results" && <ResultsTab p={p} meta={meta} onFindModule={(cri) => setParam({ tab: "analyses", q: cri, run: null })} />}
          {tab === "analyses" && (p.area ? (
            <AnalysesTab project={p} meta={meta} phase={phase} setPhase={(v) => setParam({ phase: v })}
              query={params.get("q") ?? ""} setQuery={(v) => setParam({ q: v })}
              runId={runId} openRun={openRun} onReview={review} onOpenTable={setTable}
              view={view} setView={(v) => setParam({ view: v === "data" ? "data" : null, ...(params.get("tab") === "satellite" ? { tab: "analyses" } : {}) })}
              dataCount={Object.keys(sat).length}
              dataLayers={satGroups.length === 0 ? <p className="muted">Loading the data layers…</p>
                : <DataLayers code={p.code} groups={satGroups} on={sat} setOn={setSat} errors={satErrors} loading={satLoading} phase={phase} />} />
          ) : <p className="muted">Analyses and data layers need an area of influence. {p.permissions.can_edit && <Link className="text-link" to={`/projects/${p.code}/edit`}>Add one</Link>}</p>)}
          {tab === "evidence" && <EvidenceTab items={evidence.data ?? []} meta={meta} canReview={canReview} onReview={review} onOpenRun={(id) => openRun(id)} />}
          {tab === "documents" && <DocumentsTab p={p} meta={meta} />}
          {tab === "activity" && <ActivityTab p={p} />}
          </div>
        </aside>

        <div className="pw-map">
          <ProjectMap area={showArea ? p.area?.geometry ?? null : null} fitBbox={fit} images={images} vectors={vectors} rasters={rasters} vectorTiles={vectorTiles} areaStyle={styles.area} basemapVisible={styles.basemap.visible} background={styles.basemap.background} onRastersLoading={setTilesLoading} onMap={setMapRef} onExport={() => setPrinting(true)}>
            <LayerPanel showArea={showArea} onToggleArea={() => setShowArea((v) => !v)} run={run} hidden={hiddenNow} onToggle={toggle} onClearRun={() => openRun(null)}
              styles={styles} setStyles={setStyles} satLayers={satLayers.filter((l) => sat[l.id])} sat={sat} setSat={setSat} satLoading={satLoading} />
            {table && <TableDrawer table={table} onClose={() => setTable(null)} />}
          </ProjectMap>
          {printing && mapRef && (
            <Suspense fallback={null}>
              <PrintDialog map={mapRef} code={p.code} context={printContext()} legend={legend} areaBbox={p.area?.bbox ?? null}
                countryBbox={meta?.countries.find((c) => c.iso3 === p.country_iso3)?.bbox ?? null} ramp={ramp} onClose={() => setPrinting(false)} />
            </Suspense>
          )}
        </div>
      </div>
    </div>
  );
}

/** Project identity, status and workflow actions, pinned at the top of the side panel. */
function Header({ p, meta }: { p: Project; meta: ReturnType<typeof useMeta>["data"] }) {
  const setProject = useSetProject();
  const navigate = useNavigate();
  const toast = useToast();
  const confirm = useConfirm();
  const [returning, setReturning] = useState(false);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const perms = p.permissions;

  async function act(action: "submit" | "return" | "publish", body: object = {}) {
    setBusy(true);
    try {
      const res = await api<{ project: Project }>(`/api/projects/${p.code}/${action}/`, { method: "POST", body });
      setProject(res.project);
      setReturning(false); setComment("");
      toast({ submit: "Submitted for review.", return: "Returned to the owner.", publish: "Published." }[action], "success");
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Couldn't do that.", "error");
    } finally { setBusy(false); }
  }
  async function remove() {
    if (!(await confirm({ title: `Delete the draft ${p.code}?`, message: "The project, its area of influence, results framework and analyses are removed. This can't be undone.", confirmLabel: "Delete draft", tone: "danger" }))) return;
    await api(`/api/projects/${p.code}/`, { method: "DELETE" });
    toast(`${p.code} deleted.`, "success");
    navigate("/projects");
  }

  return (
    <header className="pw-head">
      <div className="pw-head-title">
        <p>
          <Link className="icon-btn icon-btn-xs" to="/projects" aria-label="Back to projects" title="Projects"><ChevronLeft aria-hidden="true" /></Link>
          <span className="pw-code">{p.code}</span><StatusChip status={p.status} />
        </p>
        <h1 title={p.title}>{p.title}</h1>
        <p className="muted small">{p.country_name} · {label(meta?.sectors, p.sector) || "Sector not set"} · {p.stage ? label(meta?.stages, p.stage) : "Stage not set"}</p>
      </div>
      <div className="pw-head-actions">
        {perms.can_edit && <Link className="btn btn-outline btn-sm" to={`/projects/${p.code}/edit`}><Pencil aria-hidden="true" />Edit</Link>}
        {perms.can_submit && <button className="btn btn-dark btn-sm" disabled={busy || p.missing_to_submit.length > 0} onClick={() => act("submit")}><Send aria-hidden="true" />Submit for review</button>}
        {perms.can_return && <button className="btn btn-outline btn-sm" disabled={busy} onClick={() => setReturning((v) => !v)}><Undo2 aria-hidden="true" />Return</button>}
        {perms.can_publish && <button className="btn btn-dark btn-sm" disabled={busy || p.missing_to_submit.length > 0} onClick={() => act("publish")}><CheckCircle2 aria-hidden="true" />Publish</button>}
        {perms.can_delete && <button className="icon-btn" aria-label="Delete draft" title="Delete draft" onClick={remove}><Trash2 aria-hidden="true" /></button>}
      </div>
      {returning && (
        <form className="return-box pw-return" onSubmit={(e) => { e.preventDefault(); act("return", { comment }); }}>
          <label htmlFor="ret">What needs changing?</label>
          <textarea id="ret" className="input" rows={3} value={comment} onChange={(e) => setComment(e.target.value)} required />
          <div><button className="btn btn-dark btn-sm" disabled={busy || !comment.trim()}>Return to owner</button> <button type="button" className="btn btn-outline btn-sm" onClick={() => setReturning(false)}>Cancel</button></div>
        </form>
      )}
    </header>
  );
}
