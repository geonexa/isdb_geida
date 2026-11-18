import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, ChevronDown, ChevronLeft, ChevronRight, Copy, Eye, FileText, Link2, Loader2, Plus, Trash2, Wand2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/shared/api/client";
import { useConfirm } from "@/shared/components/Confirm";
import { useToast } from "@/shared/components/Toasts";
import type { Project } from "@/features/projects/types";

/** Reports: pick analysis runs, write a summary, generate frozen versions as a web report and a PDF, share a link. */

type Version = {
  id: number; number: number; status: "queued" | "building" | "done" | "failed"; error: string; pages: number;
  size_bytes: number; created: string; created_by: string; finished: string | null; html_url: string | null; pdf_url: string | null;
};
type Section = { run: number; outputs: string[] | null; note: string };
type Content = { summary: string; sections: Section[]; options: { project: boolean; annex: boolean; basemap: "light" | "satellite" } };
type Report = {
  id: number; project: string; title: string; subtitle: string; author: string; created: string; updated: string;
  content: Content; can_edit: boolean; can_manage: boolean;
  share: { active: boolean; url: string | null; expires: string | null };
  versions?: Version[]; latest?: Version | null;
  /** The newest finished version (its web report and PDF), in the list. */
  latest_done?: Version | null;
};
type RunOutput = { name: string; type: string; kind: string; title: string };
type RunItem = {
  id: number; module: string; title: string; category: string; category_title: string; color: string;
  created: string; created_by: string; summary: string; outputs: RunOutput[];
};

const BUSY = new Set(["queued", "building"]);
const EMPTY: Content = { summary: "", sections: [], options: { project: true, annex: true, basemap: "satellite" } };
const fmtDate = (s: string) => new Date(s).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
const fmtSize = (b: number) => (b < 1024 * 1024 ? `${Math.max(1, Math.round(b / 1024))} KB` : `${(b / 1024 / 1024).toFixed(1)} MB`);

/** What a newly ticked run shows: its figures, first map, first table and summary. */
function defaultOutputs(run: RunItem): string[] {
  const firstMap = run.outputs.find((o) => o.kind === "Map");
  const firstTable = run.outputs.find((o) => o.kind === "Table");
  return [...run.outputs.filter((o) => o.kind === "Figures").map((o) => o.name), firstMap?.name, firstTable?.name, "summary"]
    .filter((x): x is string => !!x);
}

function useReports(code: string) {
  return useQuery({
    queryKey: ["reports", code],
    queryFn: () => api<{ reports: Report[]; can_create: boolean }>(`/api/reports/${code}/`),
    refetchInterval: (q) => (q.state.data?.reports.some((r) => r.latest && BUSY.has(r.latest.status)) ? 3000 : false),
  });
}

function useReport(id: number | null) {
  return useQuery({
    queryKey: ["report", id],
    queryFn: () => api<{ report: Report }>(`/api/reports/${id}/`).then((d) => d.report),
    enabled: id != null,
    refetchInterval: (q) => (q.state.data?.versions?.some((v) => BUSY.has(v.status)) ? 2500 : false),
  });
}

export function ReportsTab({ p }: { p: Project }) {
  const [open, setOpen] = useState<number | "new" | null>(null);
  const list = useReports(p.code);
  if (open != null) return <ReportEditor p={p} id={open === "new" ? null : open} onBack={() => setOpen(null)} onCreated={(id) => setOpen(id)} />;
  const reports = list.data?.reports ?? [];
  return (
    <div className="rep">
      <p className="muted rep-intro">Bring the project's analyses together in a report you can download as a PDF or share as a web page. Each generated version is kept as it was.</p>
      {list.data?.can_create && (
        <button type="button" className="btn btn-dark btn-sm" onClick={() => setOpen("new")}><Plus aria-hidden="true" />New report</button>
      )}
      {list.isPending && <p className="muted"><Loader2 className="rep-spin" aria-hidden="true" /> Loading reports…</p>}
      {list.isError && <p className="field-error">{(list.error as Error).message}</p>}
      {list.data && reports.length === 0 && <p className="muted rep-empty">No reports yet.</p>}
      <ul className="rep-list">
        {reports.map((r) => (
          <li key={r.id}>
            <button type="button" className="rep-card" onClick={() => setOpen(r.id)}>
              <FileText aria-hidden="true" />
              <span className="rep-card-main">
                <strong>{r.title}</strong>
                {r.subtitle && <span>{r.subtitle}</span>}
                <small>
                  {r.content.sections.length} {r.content.sections.length === 1 ? "analysis" : "analyses"} · {r.author} · updated {fmtDate(r.updated)}
                </small>
              </span>
              <VersionBadge v={r.latest ?? null} />
              <ChevronRight aria-hidden="true" />
            </button>
            {r.latest_done?.html_url && (
              <div className="rep-card-links">
                <span className="muted">v{r.latest_done.number}</span>
                <a className="btn btn-outline btn-sm" href={r.latest_done.html_url} target="_blank" rel="noopener"><Eye aria-hidden="true" />Web report</a>
                {r.latest_done.pdf_url && <a className="btn btn-dark btn-sm" href={r.latest_done.pdf_url} target="_blank" rel="noopener"><FileText aria-hidden="true" />PDF</a>}
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function VersionBadge({ v }: { v: Version | null }) {
  if (!v) return <span className="rep-badge">Not generated</span>;
  if (BUSY.has(v.status)) return <span className="rep-badge is-busy"><Loader2 className="rep-spin" aria-hidden="true" />v{v.number} generating</span>;
  if (v.status === "failed") return <span className="rep-badge is-bad">v{v.number} failed</span>;
  return <span className="rep-badge is-ok">v{v.number} · {v.pages} pages</span>;
}

function ReportEditor({ p, id, onBack, onCreated }: { p: Project; id: number | null; onBack: () => void; onCreated: (id: number) => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const toastOk = (t: string) => toast(t, "success");
  const toastErr = (t: string) => toast(t, "error");
  const confirm = useConfirm();
  const report = useReport(id);
  const runs = useQuery({
    queryKey: ["report-runs", p.code],
    queryFn: () => api<{ runs: RunItem[] }>(`/api/reports/${p.code}/runs/`).then((d) => d.runs),
  });
  const [title, setTitle] = useState("");
  const [subtitle, setSubtitle] = useState("");
  const [content, setContent] = useState<Content>(EMPTY);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [loadedId, setLoadedId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [expiry, setExpiry] = useState("30");

  // Load the saved report into the form once (and again after switching reports).
  useEffect(() => {
    if (report.data && report.data.id !== loadedId) {
      setTitle(report.data.title);
      setSubtitle(report.data.subtitle);
      setContent({ ...EMPTY, ...report.data.content, options: { ...EMPTY.options, ...report.data.content.options } });
      setLoadedId(report.data.id);
      setDirty(false);
    }
  }, [report.data, loadedId]);

  const runById = useMemo(() => new Map((runs.data ?? []).map((r) => [r.id, r])), [runs.data]);
  const grouped = useMemo(() => {
    const g = new Map<string, { title: string; color: string; runs: RunItem[] }>();
    for (const r of runs.data ?? []) {
      if (!g.has(r.category)) g.set(r.category, { title: r.category_title, color: r.color, runs: [] });
      g.get(r.category)!.runs.push(r);
    }
    return [...g.values()];
  }, [runs.data]);

  const canEdit = id == null || !!report.data?.can_edit;
  const included = new Map(content.sections.map((s, i) => [s.run, i]));
  const change = (next: Partial<Content>) => { setContent((c) => ({ ...c, ...next })); setDirty(true); };
  const setSection = (run: number, patch: Partial<Section>) =>
    change({ sections: content.sections.map((s) => (s.run === run ? { ...s, ...patch } : s)) });

  const toggleRun = (r: RunItem) => {
    if (included.has(r.id)) change({ sections: content.sections.filter((s) => s.run !== r.id) });
    else change({ sections: [...content.sections, { run: r.id, outputs: defaultOutputs(r), note: "" }] });
  };
  const move = (i: number, d: -1 | 1) => {
    const next = [...content.sections];
    const j = i + d;
    if (j < 0 || j >= next.length) return;
    [next[i], next[j]] = [next[j], next[i]];
    change({ sections: next });
  };
  const toggleOutput = (s: Section, name: string) => {
    const r = runById.get(s.run);
    const cur = s.outputs ?? (r ? defaultOutputs(r) : []);
    setSection(s.run, { outputs: cur.includes(name) ? cur.filter((n) => n !== name) : [...cur, name] });
  };

  /** Save the form; returns the report id (creating the report the first time). */
  const save = async (): Promise<number | null> => {
    if (!title.trim()) { setError("Give the report a title."); return null; }
    setSaving(true);
    setError("");
    try {
      const body = { title, subtitle, content };
      if (id == null) {
        const d = await api<{ report: Report }>(`/api/reports/${p.code}/`, { method: "POST", body });
        qc.invalidateQueries({ queryKey: ["reports", p.code] });
        setDirty(false);
        onCreated(d.report.id);
        return d.report.id;
      }
      const d = await api<{ report: Report }>(`/api/reports/${id}/`, { method: "PATCH", body });
      qc.setQueryData(["report", id], d.report);
      qc.invalidateQueries({ queryKey: ["reports", p.code] });
      setDirty(false);
      return id;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The report couldn't be saved.");
      return null;
    } finally {
      setSaving(false);
    }
  };

  const preview = async () => {
    const rid = dirty || id == null ? await save() : id;
    if (rid != null) window.open(`/api/reports/${rid}/preview/`, "_blank", "noopener");
  };

  const generate = async () => {
    const rid = dirty || id == null ? await save() : id;
    if (rid == null) return;
    try {
      const d = await api<{ version: Version; problem: string | null }>(`/api/reports/${rid}/generate/`, { method: "POST", body: {} });
      if (d.version.status === "failed") toastErr(d.version.error);
      else toastOk(`Generating version ${d.version.number}…`);
      qc.invalidateQueries({ queryKey: ["report", rid] });
      qc.invalidateQueries({ queryKey: ["reports", p.code] });
    } catch (e) {
      toastErr(e instanceof ApiError ? e.message : "The report couldn't be generated.");
    }
  };

  const share = async (on: boolean) => {
    if (id == null) return;
    try {
      const d = await api<{ report: Report }>(`/api/reports/${id}/share/`, on
        ? { method: "POST", body: { expires_days: expiry === "none" ? null : Number(expiry) } }
        : { method: "DELETE" });
      qc.setQueryData(["report", id], d.report);
      if (on && d.report.share.url) {
        await navigator.clipboard?.writeText(location.origin + d.report.share.url).catch(() => undefined);
        toastOk("Share link created and copied.");
      }
    } catch (e) {
      toastErr(e instanceof ApiError ? e.message : "The link couldn't be changed.");
    }
  };

  const remove = async () => {
    if (id == null || !report.data) return;
    const ok = await confirm({
      title: "Delete this report?",
      message: `“${report.data.title}” and all its versions (PDFs and web pages) will be deleted, and its share link will stop working. This can't be undone.`,
      confirmLabel: "Delete report", tone: "danger",
    });
    if (!ok) return;
    try {
      await api(`/api/reports/${id}/`, { method: "DELETE" });
      qc.invalidateQueries({ queryKey: ["reports", p.code] });
      onBack();
    } catch (e) {
      toastErr(e instanceof ApiError ? e.message : "The report couldn't be deleted.");
    }
  };

  if (id != null && report.isPending) return <p className="muted"><Loader2 className="rep-spin" aria-hidden="true" /> Loading…</p>;
  const versions = report.data?.versions ?? [];
  const shareUrl = report.data?.share.url ? location.origin + report.data.share.url : "";

  return (
    <div className="rep rep-editor">
      <button type="button" className="rep-back" onClick={onBack}><ChevronLeft aria-hidden="true" />All reports</button>

      <div className="field"><label htmlFor="rep-title">Title</label>
        <input id="rep-title" className="input" value={title} disabled={!canEdit} placeholder="e.g. Site screening report"
          onChange={(e) => { setTitle(e.target.value); setDirty(true); }} /></div>
      <div className="field"><label htmlFor="rep-sub">Subtitle <span className="muted">(optional)</span></label>
        <input id="rep-sub" className="input" value={subtitle} disabled={!canEdit} placeholder="e.g. Annex to the PPRR"
          onChange={(e) => { setSubtitle(e.target.value); setDirty(true); }} /></div>
      <div className="field"><label htmlFor="rep-sum">Summary</label>
        <textarea id="rep-sum" className="input rep-textarea" rows={5} value={content.summary} disabled={!canEdit}
          placeholder="What the analyses show for the project, in your words. Each analysis' own summary is listed after it."
          onChange={(e) => change({ summary: e.target.value })} /></div>

      <h3 className="rep-h">Analyses <span className="muted">({content.sections.length} included)</span></h3>
      {runs.isPending && <p className="muted"><Loader2 className="rep-spin" aria-hidden="true" /> Loading runs…</p>}
      {runs.data && runs.data.length === 0 && <p className="muted">No finished analyses yet. Run analyses in the Analyses tab first.</p>}

      {content.sections.length > 0 && (
        <ol className="rep-order">
          {content.sections.map((s, i) => {
            const r = runById.get(s.run);
            if (!r) return null;
            const outs = s.outputs ?? defaultOutputs(r);
            const isOpen = expanded === r.id;
            return (
              <li key={s.run} style={{ ["--cat" as string]: r.color }}>
                <div className="rep-order-row">
                  <span className="rep-order-no">{i + 1}</span>
                  <button type="button" className="rep-order-title" onClick={() => setExpanded(isOpen ? null : r.id)} aria-expanded={isOpen}>
                    <strong>{r.title}</strong><small>#{r.id} · {fmtDate(r.created)} · {outs.filter((n) => n !== "summary" && n !== "method").length} items</small>
                    <ChevronDown aria-hidden="true" className={isOpen ? "is-open" : ""} />
                  </button>
                  {canEdit && <>
                    <button type="button" className="icon-btn" title="Move up" disabled={i === 0} onClick={() => move(i, -1)}><ArrowUp aria-hidden="true" /></button>
                    <button type="button" className="icon-btn" title="Move down" disabled={i === content.sections.length - 1} onClick={() => move(i, 1)}><ArrowDown aria-hidden="true" /></button>
                    <button type="button" className="icon-btn" title="Remove from the report" onClick={() => toggleRun(r)}><Trash2 aria-hidden="true" /></button>
                  </>}
                </div>
                {isOpen && (
                  <div className="rep-order-body">
                    <p className="rep-sub">Show in the report</p>
                    <div className="rep-chips">
                      {[...r.outputs, { name: "summary", kind: "Text", title: "Run summary", type: "text" }, { name: "method", kind: "Text", title: "Method in full", type: "text" }].map((o) => (
                        <label key={o.name} className={`rep-chip${outs.includes(o.name) ? " is-on" : ""}`}>
                          <input type="checkbox" checked={outs.includes(o.name)} disabled={!canEdit} onChange={() => toggleOutput(s, o.name)} />
                          <em>{o.kind}</em>{o.title}
                        </label>
                      ))}
                    </div>
                    <div className="field"><label htmlFor={`note-${r.id}`}>Note <span className="muted">(optional, shown at the top of the section)</span></label>
                      <textarea id={`note-${r.id}`} className="input rep-textarea" rows={2} value={s.note} disabled={!canEdit}
                        placeholder="What this means for the project"
                        onChange={(e) => setSection(r.id, { note: e.target.value })} /></div>
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {grouped.length > 0 && canEdit && (
        <details className="rep-pick" open={content.sections.length === 0}>
          <summary>Add analyses</summary>
          {grouped.map((g) => (
            <div key={g.title} className="rep-pick-group" style={{ ["--cat" as string]: g.color }}>
              <p className="rep-pick-cat"><i />{g.title}</p>
              {g.runs.map((r) => (
                <label key={r.id} className="check rep-pick-run">
                  <input type="checkbox" className="checkbox" checked={included.has(r.id)} onChange={() => toggleRun(r)} />
                  <span><strong>{r.title}</strong> <small className="muted">#{r.id} · {fmtDate(r.created)}{r.created_by ? ` · ${r.created_by}` : ""}</small>
                    {r.summary && <small className="rep-pick-sum">{r.summary}</small>}</span>
                </label>
              ))}
            </div>
          ))}
        </details>
      )}

      <h3 className="rep-h">Options</h3>
      <div className="rep-opts">
        <label className="check"><input type="checkbox" className="checkbox" checked={content.options.project} disabled={!canEdit}
          onChange={(e) => change({ options: { ...content.options, project: e.target.checked } })} />Project details and results framework</label>
        <label className="check"><input type="checkbox" className="checkbox" checked={content.options.annex} disabled={!canEdit}
          onChange={(e) => change({ options: { ...content.options, annex: e.target.checked } })} />Annex: data sources and notes</label>
        <div className="field rep-basemap"><label htmlFor="rep-bm">Maps</label>
          <select id="rep-bm" className="input" value={content.options.basemap} disabled={!canEdit}
            onChange={(e) => change({ options: { ...content.options, basemap: e.target.value as "light" | "satellite" } })}>
            <option value="satellite">Satellite imagery (Esri)</option>
            <option value="light">Light basemap (clean in print)</option>
          </select></div>
      </div>

      {error && <p className="field-error">{error}</p>}
      {canEdit && (
        <div className="rep-actions">
          <button type="button" className="btn btn-dark btn-sm" disabled={saving} onClick={generate}><Wand2 aria-hidden="true" />Generate PDF and web report</button>
          <button type="button" className="btn btn-outline btn-sm" disabled={saving} onClick={preview}><Eye aria-hidden="true" />Preview</button>
          <button type="button" className="btn btn-outline btn-sm" disabled={saving || (!dirty && id != null)} onClick={() => void save()}>{saving ? "Saving…" : dirty || id == null ? "Save" : "Saved"}</button>
        </div>
      )}

      {id != null && (
        <>
          <h3 className="rep-h">Versions</h3>
          {versions.length === 0 && <p className="muted">Not generated yet. Generating freezes the report as it is now: later changes to the project or its runs don't change a version.</p>}
          <ul className="rep-versions">
            {versions.map((v) => (
              <li key={v.id}>
                <div><strong>Version {v.number}</strong>
                  <small className="muted">{fmtDate(v.created)} · {v.created_by}{v.status === "done" ? ` · ${v.pages} pages · ${fmtSize(v.size_bytes)}` : ""}</small>
                  {v.status === "failed" && <small className="field-error">{v.error}</small>}
                </div>
                {BUSY.has(v.status) ? <span className="rep-badge is-busy"><Loader2 className="rep-spin" aria-hidden="true" />{v.status === "queued" ? "Queued" : "Generating"}</span>
                  : v.status === "done" ? (
                    <span className="rep-version-links">
                      <a className="btn btn-outline btn-sm" href={v.html_url!} target="_blank" rel="noopener"><Eye aria-hidden="true" />Web report</a>
                      <a className="btn btn-dark btn-sm" href={v.pdf_url!} target="_blank" rel="noopener"><FileText aria-hidden="true" />PDF</a>
                    </span>
                  ) : <span className="rep-badge is-bad">Failed</span>}
              </li>
            ))}
          </ul>

          {report.data?.can_manage && (
            <>
              <h3 className="rep-h">Share</h3>
              {report.data.share.active ? (
                <div className="rep-share">
                  <p className="muted">Anyone with this link can open the latest version, without signing in{report.data.share.expires ? `, until ${fmtDate(report.data.share.expires)}` : ""}.</p>
                  <div className="rep-share-row">
                    <input className="input" readOnly value={shareUrl} onFocus={(e) => e.target.select()} aria-label="Share link" />
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => navigator.clipboard?.writeText(shareUrl).then(() => toastOk("Link copied."))}><Copy aria-hidden="true" />Copy</button>
                    <button type="button" className="btn btn-outline btn-sm" onClick={() => share(false)}>Revoke</button>
                  </div>
                </div>
              ) : (
                <div className="rep-share-row">
                  <select className="input" value={expiry} onChange={(e) => setExpiry(e.target.value)} aria-label="Link lasts">
                    <option value="7">Link lasts 7 days</option>
                    <option value="30">Link lasts 30 days</option>
                    <option value="90">Link lasts 90 days</option>
                    <option value="none">No end date</option>
                  </select>
                  <button type="button" className="btn btn-outline btn-sm" disabled={!versions.some((v) => v.status === "done")} onClick={() => share(true)}><Link2 aria-hidden="true" />Create share link</button>
                </div>
              )}
              <button type="button" className="rep-delete" onClick={remove}><Trash2 aria-hidden="true" />Delete report</button>
            </>
          )}
        </>
      )}
    </div>
  );
}
