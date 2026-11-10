import { CircleAlert, Plus, Sparkles, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { api, ApiError } from "@/shared/api/client";
import { FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { label, useSetProject } from "@/features/projects/data";
import { CriPicker } from "@/features/projects/steps/CriPicker";
import type { CRI, Indicator, Meta, Project } from "@/features/projects/types";

type Props = { meta: Meta; project: Project; onBack: () => void; onNext: () => void };
type Row = Omit<Indicator, "baseline_value" | "baseline_year" | "target_value" | "target_year"> & {
  baseline_value: string; baseline_year: string; target_value: string; target_year: string; key: number;
};

const TA = new Set(["17.1", "17.2", "17.4"]);
let seq = 0;
const blank = (): Row => ({
  key: ++seq, level: "output", statement: "", unit: "", cri: null, tier: "project_specific",
  baseline_value: "", baseline_year: "", target_value: "", target_year: "",
  means_of_verification: "", sex_disaggregated: false, geo_role: "none",
});
const toRow = (i: Indicator): Row => ({
  ...i, key: ++seq,
  baseline_value: i.baseline_value?.toString() ?? "", baseline_year: i.baseline_year?.toString() ?? "",
  target_value: i.target_value?.toString() ?? "", target_year: i.target_year?.toString() ?? "",
});
const normUnit = (u: string) => u.toLowerCase().replace("²", "2").replace(/\s/g, "");

export function StepResults({ meta, project, onBack, onNext }: Props) {
  const toast = useToast();
  const setProject = useSetProject();
  const [rows, setRows] = useState<Row[]>(project.indicators.length ? project.indicators.map(toRow) : [blank()]);
  const [errors, setErrors] = useState<Record<string, Record<string, string[]>>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const patch = (key: number, p: Partial<Row>) => setRows((r) => r.map((x) => (x.key === key ? { ...x, ...p } : x)));
  // Picking a CRI fills in name, unit, tier, role and the sex flag; the user can still change them.
  const pickCri = (row: Row, c: CRI | null) => patch(row.key, c ? {
    cri: c,
    statement: row.statement || c.name,
    unit: row.unit || c.unit,
    tier: TA.has(c.code) ? "ta_cri" : "project_cri",
    geo_role: c.geida_role,
    sex_disaggregated: c.sex_disaggregated === "yes",
  } : { cri: null, tier: "project_specific", geo_role: "none" });

  const support = useMemo(() => {
    const seen = new Map<string, CRI>();
    rows.forEach((r) => { if (r.cri && r.cri.geida_role !== "none") seen.set(r.cri.code, r.cri); });
    return [...seen.values()];
  }, [rows]);

  async function save(next: boolean) {
    setBusy(true); setAlert(null); setErrors({});
    const body = rows
      .filter((r) => r.statement.trim() || r.cri)
      .map((r) => ({ ...r, cri: r.cri?.code ?? null, key: undefined, warnings: undefined }));
    try {
      const res = await api<{ project: Project }>(`/api/projects/${project.code}/indicators/`, { method: "PUT", body: { indicators: body } });
      setProject(res.project);
      setRows(res.project.indicators.length ? res.project.indicators.map(toRow) : [blank()]);
      toast(`Results Framework saved (${res.project.indicators.length} indicator${res.project.indicators.length === 1 ? "" : "s"}).`, "success");
      if (next) onNext();
    } catch (e) {
      if (e instanceof ApiError) { setErrors((e.data.errors as typeof errors) ?? {}); setAlert(e.message); }
      else setAlert("Couldn't save.");
    } finally { setBusy(false); }
  }

  const err = (i: number, f: string) => errors[String(i)]?.[f];

  return (
    <div className="wizard-body is-wide">
      <div className="wizard-panel">
        <h2>Results Framework</h2>
        <p className="muted">Indicators from the project logframe. Link each to an IsDB Core Result Indicator (CRI) where one applies; leave the CRI blank for project-specific indicators.</p>
        <FormAlert text={alert} />
        <ol className="ind-list">
          {rows.map((r, i) => {
            const unitWarn = r.cri && r.cri.unit && r.unit && normUnit(r.cri.unit) !== normUnit(r.unit)
              ? `CRI ${r.cri.code} is reported in ${r.cri.unit}; this indicator uses ${r.unit}. GEIDA will convert.` : null;
            const warnings = [...new Set([...(unitWarn ? [unitWarn] : []), ...(r.warnings ?? []).filter((w) => !/converting/.test(w))])];
            return (
              <li key={r.key} className="ind-card">
                <div className="ind-top">
                  <span className="ind-n">{i + 1}</span>
                  <select className="input ind-level" value={r.level} onChange={(e) => patch(r.key, { level: e.target.value })} aria-label="Level">
                    {meta.levels.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                  <div className="ind-cri"><CriPicker value={r.cri} onChange={(c) => pickCri(r, c)} /></div>
                  <button type="button" className="icon-btn" aria-label={`Remove indicator ${i + 1}`} onClick={() => setRows((x) => (x.length > 1 ? x.filter((y) => y.key !== r.key) : [blank()]))}><Trash2 aria-hidden="true" /></button>
                </div>
                <div className="ind-grid">
                  <label className="span-4">Statement<input className="input" value={r.statement} onChange={(e) => patch(r.key, { statement: e.target.value })} aria-invalid={!!err(i, "statement")} /></label>
                  <label>Unit<input className="input" value={r.unit} onChange={(e) => patch(r.key, { unit: e.target.value })} /></label>
                  <label>Tier
                    <select className="input" value={r.tier} onChange={(e) => patch(r.key, { tier: e.target.value })}>
                      {meta.tiers.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </label>
                  <label>Baseline<input className="input" inputMode="decimal" value={r.baseline_value} onChange={(e) => patch(r.key, { baseline_value: e.target.value })} aria-invalid={!!err(i, "baseline_value")} /></label>
                  <label>Baseline year<input className="input" inputMode="numeric" placeholder="2024" value={r.baseline_year} onChange={(e) => patch(r.key, { baseline_year: e.target.value })} aria-invalid={!!err(i, "baseline_year")} /></label>
                  <label>Target<input className="input" inputMode="decimal" value={r.target_value} onChange={(e) => patch(r.key, { target_value: e.target.value })} aria-invalid={!!err(i, "target_value")} /></label>
                  <label>Target year<input className="input" inputMode="numeric" placeholder="2028" value={r.target_year} onChange={(e) => patch(r.key, { target_year: e.target.value })} aria-invalid={!!err(i, "target_year")} /></label>
                  <label className="span-2">Geospatial role
                    <select className="input" value={r.geo_role} onChange={(e) => patch(r.key, { geo_role: e.target.value })}>
                      {meta.geo_roles.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                    </select>
                  </label>
                  <label className="span-4">Means of verification<input className="input" value={r.means_of_verification} onChange={(e) => patch(r.key, { means_of_verification: e.target.value })} /></label>
                  <label className="ind-check span-2"><input type="checkbox" checked={r.sex_disaggregated} onChange={(e) => patch(r.key, { sex_disaggregated: e.target.checked })} />Report male / female values</label>
                </div>
                {errors[String(i)] && <p className="field-error"><CircleAlert aria-hidden="true" />{Object.values(errors[String(i)]).flat().join(" ")}</p>}
                {warnings.length > 0 && <ul className="ind-warn">{warnings.map((w) => <li key={w}>{w}</li>)}</ul>}
              </li>
            );
          })}
        </ol>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => setRows((r) => [...r, blank()])}><Plus aria-hidden="true" />Add indicator</button>
        <div className="wizard-foot">
          <button type="button" className="btn btn-outline" onClick={onBack}>Back</button>
          <span className="foot-right">
            <button type="button" className="btn btn-outline" onClick={() => save(false)} disabled={busy}>Save</button>
            <button type="button" className="btn btn-dark" onClick={() => save(true)} disabled={busy}>{busy ? "Saving…" : "Save and continue"}</button>
          </span>
        </div>
      </div>
      <aside className="support-panel">
        <h3><Sparkles aria-hidden="true" />GEIDA can help with</h3>
        {support.length === 0 ? (
          <p className="muted small">Link indicators to CRIs to see which ones GEIDA's analyses can measure, estimate or verify for this project.</p>
        ) : (
          <ul>
            {support.map((c) => (
              <li key={c.code}>
                <span className={`role role-${c.geida_role}`}>{label(meta.geo_roles, c.geida_role)}</span>
                <strong>CRI {c.code}</strong> {c.name}
                {c.candidate_module && <span className="muted small">Analysis: {c.candidate_module}</span>}
              </li>
            ))}
          </ul>
        )}
        {support.length > 0 && <p className="muted small">Whether each analysis can run for this project is checked once the analysis modules are added.</p>}
      </aside>
    </div>
  );
}
