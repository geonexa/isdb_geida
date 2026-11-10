import { ArrowRight, CircleAlert, ExternalLink, FileText, Sparkles } from "lucide-react";

import { km2, label, MISSING_LABELS } from "@/features/projects/data";
import type { Evidence, Meta, Project, Run } from "@/features/projects/types";
import { EvidenceList } from "@/features/projects/workspace/RunParts";

const fmtDate = (s: string | null) => (s ? new Date(s).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" }) : "—");
const num = (v: number | null, y: number | null) => (v == null ? "—" : `${v.toLocaleString()}${y ? ` (${y})` : ""}`);

export function OverviewTab({ p, meta, runs, evidence, go }: {
  p: Project; meta?: Meta; runs: Run[]; evidence: Evidence[]; go: (tab: string) => void;
}) {
  const accepted = evidence.filter((e) => e.status === "accepted").length;
  const proposed = evidence.filter((e) => e.status === "proposed").length;
  return (
    <div className="pw-stack">
      {p.status === "draft" && p.review_comment && <div className="alert alert-warn" role="note"><CircleAlert aria-hidden="true" /><div><strong>Returned by reviewer:</strong> {p.review_comment}</div></div>}
      {p.missing_to_submit.length > 0 && p.permissions.can_edit && (
        <div className="alert alert-info" role="note"><CircleAlert aria-hidden="true" /><div>Still needed before review: {p.missing_to_submit.map((x) => MISSING_LABELS[x] ?? x).join(", ")}.</div></div>
      )}
      <div className="pw-stats">
        <div><span>Area</span><strong>{p.area ? km2(p.area.area_km2) : "—"}</strong></div>
        <button type="button" onClick={() => go("results")}><span>Indicators</span><strong>{p.indicators.length}</strong></button>
        <button type="button" onClick={() => go("analyses")}><span>Analysis runs</span><strong>{runs.length}</strong></button>
        <button type="button" onClick={() => go("evidence")}><span>Evidence</span><strong>{accepted}{proposed > 0 && <em> +{proposed} to review</em>}</strong></button>
      </div>

      <section>
        <h4 className="pw-h4">Area of influence</h4>
        {p.area ? (
          <>
            <p className="small">{label(meta?.area_methods, p.area.method)}{p.area.source_name ? ` · ${p.area.source_name}` : ""} · updated {fmtDate(p.area.updated)}</p>
            {p.area.notes.length > 0 && <ul className="area-notes">{p.area.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          </>
        ) : <p className="muted small">Not set yet{p.permissions.can_edit ? " — add it with Edit." : "."}</p>}
      </section>

      <section>
        <h4 className="pw-h4">Project</h4>
        <dl className="facts">
          <div><dt>Country</dt><dd>{p.country_name}</dd></div>
          <div><dt>Sector</dt><dd>{label(meta?.sectors, p.sector) || "—"}</dd></div>
          <div><dt>Cycle stage</dt><dd>{p.stage ? label(meta?.stages, p.stage) : "—"}</dd></div>
          <div><dt>Dates</dt><dd>{p.start_date || p.end_date ? `${fmtDate(p.start_date)} – ${fmtDate(p.end_date)}` : "—"}</dd></div>
          <div><dt>OTL</dt><dd>{p.otl || "—"}</dd></div>
          <div><dt>Regional hub</dt><dd>{p.hub ? label(meta?.hubs, p.hub) : "—"}</dd></div>
          <div><dt>Location</dt><dd>{p.location || "—"}</dd></div>
          <div><dt>Themes</dt><dd>{p.themes.length ? p.themes.map((t) => label(meta?.themes, t)).join(", ") : "—"}</dd></div>
          <div><dt>Source</dt><dd>{p.source === "form" ? `Submission form${p.source_info.submitted_by ? ` (${p.source_info.submitted_by})` : ""}` : p.source === "import" ? "Bulk import" : "Manual entry"} · {p.owner}</dd></div>
        </dl>
      </section>

      {p.components.length > 0 && (
        <section>
          <h4 className="pw-h4">Components</h4>
          <ol className="pw-comps">{p.components.map((c, i) => <li key={i}><strong>{c.name}</strong>{c.description && <span className="muted"> {c.description}</span>}</li>)}</ol>
        </section>
      )}
    </div>
  );
}

export function ResultsTab({ p, meta, onFindModule }: { p: Project; meta?: Meta; onFindModule: (cri: string) => void }) {
  return (
    <div className="pw-stack">
      {p.indicators.length === 0 ? <p className="muted">No indicators yet.</p> : (
        <ul className="pw-inds">
          {p.indicators.map((i) => (
            <li key={i.id ?? i.statement} className="pw-ind">
              <div className="pw-ind-top">
                <span className="pw-level">{label(meta?.levels, i.level)}</span>
                {i.cri && <span className="cri-tag is-match" title={i.cri.name}>CRI {i.cri.code}</span>}
                <span className={`role role-${i.geo_role}`}>{label(meta?.geo_roles, i.geo_role)}</span>
              </div>
              <p className="pw-ind-stmt">{i.statement}</p>
              <dl className="pw-ind-vals">
                <div><dt>Baseline</dt><dd>{num(i.baseline_value, i.baseline_year)}</dd></div>
                <div><dt>Target</dt><dd>{num(i.target_value, i.target_year)}</dd></div>
                <div><dt>GEIDA</dt><dd>{i.evidence ? <strong className="pw-ev-val" title={`${i.evidence.instrument} · data ${i.evidence.reference_date}`}>{i.evidence.value?.toLocaleString() ?? "—"}</strong> : <span className="muted">—</span>}</dd></div>
              </dl>
              <p className="muted small">{i.unit}{i.sex_disaggregated ? " · M/F" : ""} · {label(meta?.tiers, i.tier)}{i.means_of_verification ? ` · ${i.means_of_verification}` : ""}</p>
              {i.warnings?.length ? <p className="psub warn">{i.warnings[0]}</p> : null}
            </li>
          ))}
        </ul>
      )}
      {p.geida_support.length > 0 && (
        <section className="pw-support">
          <h4 className="pw-h4"><Sparkles aria-hidden="true" />GEIDA can help with</h4>
          <ul>
            {p.geida_support.map((s) => (
              <li key={s.cri}>
                <span className={`role role-${s.role}`}>{label(meta?.geo_roles, s.role)}</span>
                <span className="pw-support-name">CRI {s.cri} {s.name}</span>
                <button type="button" className="link-btn small" onClick={() => onFindModule(s.cri)}>Modules<ArrowRight className="inline-icon" aria-hidden="true" /></button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

export function EvidenceTab({ items, meta, canReview, onReview, onOpenRun }: {
  items: Evidence[]; meta?: Meta; canReview: boolean; onReview: (e: Evidence, a: "accept" | "reject") => void; onOpenRun: (id: number) => void;
}) {
  if (!items.length) {
    return <p className="muted">No evidence yet. Analysis modules linked to CRIs propose values here. Nothing is written into the Results Framework until someone accepts it.</p>;
  }
  const order = { proposed: 0, accepted: 1, rejected: 2 } as const;
  const sorted = [...items].sort((a, b) => order[a.status] - order[b.status]);
  return <EvidenceList items={sorted} meta={meta} canReview={canReview} onReview={onReview} onOpenRun={onOpenRun} />;
}

export function DocumentsTab({ p, meta }: { p: Project; meta?: Meta }) {
  if (!p.documents.length) return <p className="muted">No document links yet.</p>;
  return (
    <ul className="pw-docs">
      {p.documents.map((d) => (
        <li key={d.id ?? d.url}>
          <a href={d.url} target="_blank" rel="noopener">
            <FileText aria-hidden="true" />
            <span><strong>{d.title || label(meta?.doc_types, d.doc_type)}</strong><span className="muted small">{label(meta?.doc_types, d.doc_type)}</span></span>
            <ExternalLink className="pw-ext" aria-hidden="true" />
          </a>
        </li>
      ))}
    </ul>
  );
}

export function ActivityTab({ p }: { p: Project }) {
  return (
    <ol className="pw-timeline">
      {p.log.map((l, i) => (
        <li key={i}>
          <strong>{l.action}</strong>
          <span className="muted small">{l.user || "system"} · {new Date(l.created).toLocaleString()}</span>
          {typeof l.detail.comment === "string" && <q>{l.detail.comment}</q>}
        </li>
      ))}
    </ol>
  );
}
