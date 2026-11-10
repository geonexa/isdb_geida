import { CircleAlert, ExternalLink, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api, ApiError } from "@/shared/api/client";
import { FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { km2, label, MISSING_LABELS, useSetProject } from "@/features/projects/data";
import type { Doc, Meta, Project } from "@/features/projects/types";

type Props = { meta: Meta; project: Project; onBack: () => void; onEdit: (step: number) => void };

export function StepDocuments({ meta, project, onBack, onEdit }: Props) {
  const toast = useToast();
  const navigate = useNavigate();
  const setProject = useSetProject();
  const [docs, setDocs] = useState<Doc[]>(project.documents.length ? project.documents : [{ doc_type: "PAD", title: "", url: "" }]);
  const [errors, setErrors] = useState<Record<string, Record<string, string[]>>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const patch = (i: number, p: Partial<Doc>) => setDocs((d) => d.map((x, j) => (j === i ? { ...x, ...p } : x)));

  async function saveDocs(): Promise<Project | null> {
    setErrors({}); setAlert(null);
    try {
      const res = await api<{ project: Project }>(`/api/projects/${project.code}/documents/`, { method: "PUT", body: { documents: docs } });
      setProject(res.project);
      return res.project;
    } catch (e) {
      if (e instanceof ApiError) { setErrors((e.data.errors as typeof errors) ?? {}); setAlert(e.message); }
      else setAlert("Couldn't save.");
      return null;
    }
  }

  async function finish(submit: boolean) {
    setBusy(true);
    const p = await saveDocs();
    if (p && submit) {
      try {
        const res = await api<{ project: Project }>(`/api/projects/${project.code}/submit/`, { method: "POST", body: {} });
        setProject(res.project);
        toast(`${project.code} submitted for review.`, "success");
        navigate(`/projects/${project.code}`);
      } catch (e) {
        setAlert(e instanceof ApiError ? e.message : "Couldn't submit.");
      }
    } else if (p) {
      toast("Draft saved.", "success");
      navigate(`/projects/${project.code}`);
    }
    setBusy(false);
  }

  const missing = project.missing_to_submit;
  const rows: [string, string, number][] = [
    ["Identity", `${project.code} · ${project.country_name} · ${label(meta.sectors, project.sector) || "no sector"} · ${project.stage || "no stage"}`, 1],
    ["Area", project.area ? `${km2(project.area.area_km2)} (${label(meta.area_methods, project.area.method)})` : "Not set", 2],
    ["Themes", project.themes.length ? project.themes.map((t) => label(meta.themes, t)).join(", ") : "None", 3],
    ["Components", project.components.length ? `${project.components.length}` : "None", 3],
    ["Results Framework", project.indicators.length ? `${project.indicators.length} indicator(s), ${project.indicators.filter((i) => i.cri).length} linked to CRIs` : "None", 4],
  ];

  return (
    <div className="wizard-body is-wide">
      <div className="wizard-panel">
        <h2>Documents</h2>
        <p className="muted">Links to the project documents on SharePoint. Files stay there; GEIDA keeps the link.</p>
        <FormAlert text={alert} />
        <ul className="doc-list">
          {docs.map((d, i) => (
            <li key={i}>
              <select className="input" value={d.doc_type} onChange={(e) => patch(i, { doc_type: e.target.value })} aria-label="Document type">
                {meta.doc_types.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
              <input className="input" placeholder="Title (optional)" value={d.title} onChange={(e) => patch(i, { title: e.target.value })} aria-label="Title" />
              <input className="input" placeholder="https://isdb.sharepoint.com/…" value={d.url} onChange={(e) => patch(i, { url: e.target.value })} aria-label="Link" aria-invalid={!!errors[String(i)]} />
              {d.url.startsWith("http") ? <a className="icon-btn" href={d.url} target="_blank" rel="noopener" aria-label="Open link"><ExternalLink aria-hidden="true" /></a> : <span />}
              <button type="button" className="icon-btn" aria-label="Remove link" onClick={() => setDocs((x) => x.filter((_, j) => j !== i))}><Trash2 aria-hidden="true" /></button>
              {errors[String(i)] && <p className="field-error span-all"><CircleAlert aria-hidden="true" />{errors[String(i)].url?.[0]}</p>}
            </li>
          ))}
        </ul>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => setDocs((d) => [...d, { doc_type: "other", title: "", url: "" }])}><Plus aria-hidden="true" />Add link</button>

        <h2 className="sub-h2">Summary</h2>
        <dl className="summary">
          {rows.map(([k, v, step]) => (
            <div key={k}><dt>{k}</dt><dd>{v}</dd><button type="button" className="link-btn" onClick={() => onEdit(step)}>Edit</button></div>
          ))}
        </dl>
        {missing.length > 0 && (
          <div className="alert alert-warn" role="note"><CircleAlert aria-hidden="true" />
            <div>To submit for review, add: {missing.map((m) => MISSING_LABELS[m] ?? m).join(", ")}. You can save it as a draft meanwhile.</div>
          </div>
        )}
        <div className="wizard-foot">
          <button type="button" className="btn btn-outline" onClick={onBack}>Back</button>
          <span className="foot-right">
            <button type="button" className="btn btn-outline" onClick={() => finish(false)} disabled={busy}>Save as draft</button>
            {project.permissions.can_submit && (
              <button type="button" className="btn btn-dark" onClick={() => finish(true)} disabled={busy || missing.length > 0}><Send aria-hidden="true" />Submit for review</button>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}
