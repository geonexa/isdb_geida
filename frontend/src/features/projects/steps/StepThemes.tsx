import { Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { api, ApiError } from "@/shared/api/client";
import { FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { useSetProject } from "@/features/projects/data";
import { ProjectMap } from "@/features/projects/ProjectMap";
import type { Component, Meta, Project } from "@/features/projects/types";

type Props = { meta: Meta; project: Project; onBack: () => void; onNext: () => void };

export function StepThemes({ meta, project, onBack, onNext }: Props) {
  const toast = useToast();
  const setProject = useSetProject();
  const [themes, setThemes] = useState<string[]>(project.themes);
  const [comps, setComps] = useState<Component[]>(project.components.length ? project.components : [{ name: "", description: "" }]);
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const toggle = (t: string) => setThemes((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]));
  const setComp = (i: number, k: keyof Component, v: string) => setComps((c) => c.map((x, j) => (j === i ? { ...x, [k]: v } : x)));

  async function save() {
    setBusy(true); setAlert(null);
    try {
      const res = await api<{ project: Project }>(`/api/projects/${project.code}/`, { method: "PATCH", body: { themes, components: comps } });
      setProject(res.project);
      toast("Saved.", "success");
      onNext();
    } catch (e) {
      setAlert(e instanceof ApiError ? e.message : "Couldn't save.");
    } finally { setBusy(false); }
  }

  return (
    <div className="wizard-body">
      <div className="wizard-panel">
        <h2>Themes and components</h2>
        <p className="muted">Themes decide which analyses GEIDA offers for this project.</p>
        <FormAlert text={alert} />
        <div className="chips" role="group" aria-label="Themes">
          {meta.themes.map((t) => (
            <button key={t.value} type="button" className="chip" aria-pressed={themes.includes(t.value)} onClick={() => toggle(t.value)}>{t.label}</button>
          ))}
        </div>
        <h3 className="sub-h">Project components</h3>
        <p className="muted small">As listed in the project documents, e.g. "Rehabilitation of 45 km of main canal".</p>
        <ol className="comp-list">
          {comps.map((c, i) => (
            <li key={i}>
              <input className="input" placeholder={`Component ${i + 1}`} value={c.name} onChange={(e) => setComp(i, "name", e.target.value)} aria-label={`Component ${i + 1} name`} />
              <textarea className="input" rows={2} placeholder="Short description (optional)" value={c.description} onChange={(e) => setComp(i, "description", e.target.value)} aria-label={`Component ${i + 1} description`} />
              <button type="button" className="icon-btn" aria-label={`Remove component ${i + 1}`} onClick={() => setComps((x) => x.filter((_, j) => j !== i))}><Trash2 aria-hidden="true" /></button>
            </li>
          ))}
        </ol>
        <button type="button" className="btn btn-outline btn-sm" onClick={() => setComps((c) => [...c, { name: "", description: "" }])}><Plus aria-hidden="true" />Add component</button>
        <div className="wizard-foot">
          <button type="button" className="btn btn-outline" onClick={onBack}>Back</button>
          <button type="button" className="btn btn-dark" onClick={save} disabled={busy}>{busy ? "Saving…" : "Save and continue"}</button>
        </div>
      </div>
      <ProjectMap className="wizard-map" fitBbox={project.area?.bbox ?? meta.countries.find((c) => c.iso3 === project.country_iso3)?.bbox ?? null} area={project.area?.geometry ?? null} />
    </div>
  );
}
