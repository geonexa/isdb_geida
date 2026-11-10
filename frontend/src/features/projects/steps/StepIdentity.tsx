import { useState, type FormEvent } from "react";

import { api, ApiError } from "@/shared/api/client";
import { Field, FieldErrors, FormAlert } from "@/shared/components/Field";
import { useToast } from "@/shared/components/Toasts";
import { useSetProject } from "@/features/projects/data";
import { ProjectMap } from "@/features/projects/ProjectMap";
import type { Meta, Project } from "@/features/projects/types";
import { Link } from "react-router-dom";

type Props = { meta: Meta; project?: Project; onDone: (p: Project, created: boolean) => void };

export function StepIdentity({ meta, project, onDone }: Props) {
  const toast = useToast();
  const setProject = useSetProject();
  const [f, setF] = useState({
    code: project?.code ?? "",
    title: project?.title ?? "",
    country_iso3: project?.country_iso3 ?? "",
    sector: project?.sector ?? "",
    stage: project?.stage ?? "",
    start_date: project?.start_date ?? "",
    end_date: project?.end_date ?? "",
    otl: project?.otl ?? "",
    hub: project?.hub ?? "",
    location: project?.location ?? "",
  });
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [alert, setAlert] = useState<string | null>(null);
  const [exists, setExists] = useState<{ code: string; title: string; can_edit: boolean; visible: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));

  // Suggest the country from the code's first three letters (UGA1072 -> Uganda).
  function onCode(v: string) {
    const code = v.toUpperCase().replace(/\s/g, "");
    setF((s) => {
      const guess = meta.countries.find((c) => c.iso3 === code.slice(0, 3));
      return { ...s, code, country_iso3: s.country_iso3 || (guess ? guess.iso3 : "") };
    });
    setExists(null);
  }
  const country = meta.countries.find((c) => c.iso3 === f.country_iso3);
  const codeHint = f.code && !/^[A-Z]{3}\d{4}$/.test(f.code) ? "Most IsDB codes are three letters and four digits, e.g. UGA1072." : undefined;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true); setErrors({}); setAlert(null); setExists(null);
    try {
      const body = { ...f, start_date: f.start_date || null, end_date: f.end_date || null };
      const res = project
        ? await api<{ project: Project }>(`/api/projects/${project.code}/`, { method: "PATCH", body })
        : await api<{ project: Project }>("/api/projects/", { method: "POST", body });
      setProject(res.project);
      toast(project ? "Saved." : `${res.project.code} created as a draft.`, "success");
      onDone(res.project, !project || res.project.code !== project.code);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrors(err.fieldErrors);
        if (err.status === 409 && err.data.exists) setExists(err.data.exists as typeof exists);
        else setAlert(err.message);
      } else setAlert("Couldn't save. Check your connection and try again.");
    } finally { setBusy(false); }
  }

  return (
    <div className="wizard-body">
      <form className="wizard-panel" onSubmit={submit} noValidate>
        <h2>Identity</h2>
        <p className="muted">The minimum to start: code, title and country. Everything else can be filled in later.</p>
        <FormAlert text={alert} />
        {exists && (
          <div className="alert alert-warn" role="alert">
            <div>
              <strong>{exists.code} already exists</strong> ({exists.title}).{" "}
              {exists.can_edit ? <Link className="text-link" to={`/projects/${exists.code}/edit`}>Open it to update it</Link>
                : exists.visible ? <Link className="text-link" to={`/projects/${exists.code}`}>View it</Link>
                : "Ask its owner or a reviewer to update it."}
            </div>
          </div>
        )}
        <Field label="Project code" value={f.code} onChange={(e) => onCode(e.target.value)} errors={errors.code}
               help={codeHint ?? "e.g. UGA1072"} placeholder="UGA1072" autoComplete="off" required maxLength={20} />
        <Field label="Title" value={f.title} onChange={set("title")} errors={errors.title} required maxLength={300} />
        <div className={`field${errors.country_iso3 ? " has-error" : ""}`}>
          <label htmlFor="pc-country">Country</label>
          <select id="pc-country" className="input" value={f.country_iso3} onChange={set("country_iso3")} required>
            <option value="">Choose a member country</option>
            {meta.countries.map((c) => <option key={c.iso3} value={c.iso3}>{c.name}</option>)}
          </select>
          <FieldErrors errors={errors.country_iso3} />
        </div>
        <div className="field-row">
          <Select label="Sector" value={f.sector} onChange={set("sector")} options={meta.sectors} errors={errors.sector} />
          <Select label="Cycle stage" value={f.stage} onChange={set("stage")} options={meta.stages} errors={errors.stage} />
        </div>
        <div className="field-row">
          <Field label="Start date" type="date" value={f.start_date ?? ""} onChange={set("start_date")} errors={errors.start_date} />
          <Field label="Expected completion" type="date" value={f.end_date ?? ""} onChange={set("end_date")} errors={errors.end_date} />
        </div>
        <div className="field-row">
          <Field label="Operations team leader (OTL)" value={f.otl} onChange={set("otl")} errors={errors.otl} />
          <Select label="Regional hub" value={f.hub} onChange={set("hub")} options={meta.hubs} errors={errors.hub} />
        </div>
        <Field label="Location" value={f.location} onChange={set("location")} errors={errors.location}
               help="Villages, towns or districts, as written in the project documents." />
        <div className="wizard-foot">
          <span />
          <button className="btn btn-dark" type="submit" disabled={busy}>{busy ? "Saving…" : project ? "Save and continue" : "Create draft and continue"}</button>
        </div>
      </form>
      <ProjectMap className="wizard-map" fitBbox={country?.bbox ?? null} area={project?.area?.geometry ?? null} />
    </div>
  );
}

export function Select({ label, value, onChange, options, errors, short }: {
  label: string; value: string; onChange: (e: { target: { value: string } }) => void;
  options: { value: string; label: string }[]; errors?: string[]; short?: boolean;
}) {
  const id = `sel-${label.replace(/\W+/g, "-").toLowerCase()}`;
  return (
    <div className={`field${errors?.length ? " has-error" : ""}`}>
      <label htmlFor={id}>{label}</label>
      <select id={id} className="input" value={value} onChange={onChange}>
        <option value="">—</option>
        {options.map((o) => <option key={o.value} value={o.value}>{short ? o.value : o.label}</option>)}
      </select>
      <FieldErrors errors={errors} />
    </div>
  );
}
