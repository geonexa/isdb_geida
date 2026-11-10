import { useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Download, FileSpreadsheet, FileUp } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, Navigate } from "react-router-dom";

import { api, ApiError, upload } from "@/shared/api/client";
import { useAuth } from "@/features/auth/AuthContext";
import { FormAlert } from "@/shared/components/Field";
import { useTitle } from "@/shared/lib/dom";
import { label, useMeta } from "@/features/projects/data";
import type { ImportRow } from "@/features/projects/types";

type Preview = { token: string; kind: string; file: string; rows: ImportRow[]; unused_boundaries: string[] };
type Result = { created: number; updated: number; results: { row: number; code: string; status: string; area?: string | null; errors?: string[] }[] };

export default function ImportPage() {
  useTitle("Import projects");
  const { user, loading } = useAuth();
  const meta = useMeta();
  const qc = useQueryClient();
  const [kind, setKind] = useState<"template" | "form">("template");
  const [file, setFile] = useState<File | null>(null);
  const [zip, setZip] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [keep, setKeep] = useState<Record<number, boolean>>({});
  const [apply, setApply] = useState<Record<number, boolean>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!loading && !user) return <Navigate to="/accounts/sign-in?next=/projects/import" replace />;

  async function onPreview(e: FormEvent) {
    e.preventDefault();
    if (!file) { setAlert("Choose the Excel file."); return; }
    setBusy(true); setAlert(null); setResult(null);
    const form = new FormData();
    form.append("kind", kind);
    form.append("file", file);
    if (zip) form.append("boundaries", zip);
    try {
      const res = await upload<Preview>("/api/projects/import/preview/", form);
      setPreview(res);
      setKeep(Object.fromEntries(res.rows.map((r) => [r.row, r.action !== "error"])));
      setApply(Object.fromEntries(res.rows.map((r) => [r.row, !!r.suggestion && r.boundary !== "file"])));
    } catch (err) {
      setPreview(null);
      setAlert(err instanceof ApiError ? err.message : "Couldn't read the file.");
    } finally { setBusy(false); }
  }

  async function onCommit() {
    if (!preview) return;
    setBusy(true); setAlert(null);
    const rows = preview.rows.filter((r) => keep[r.row]).map((r) => ({ row: r.row, apply_suggestion: !!apply[r.row] }));
    try {
      const res = await api<Result>("/api/projects/import/commit/", { method: "POST", body: { token: preview.token, rows } });
      setResult(res);
      setPreview(null);
      qc.invalidateQueries({ queryKey: ["projects"] });
    } catch (err) {
      setAlert(err instanceof ApiError ? err.message : "Import failed.");
    } finally { setBusy(false); }
  }

  const n = preview ? preview.rows.filter((r) => keep[r.row]).length : 0;

  return (
    <div className="section pimport"><div className="wrap">
      <Link className="back-link" to="/projects"><ChevronLeft aria-hidden="true" />Projects</Link>
      <h1>Import projects</h1>
      <p className="muted">Load several projects at once. Every row is checked first; nothing is saved until you confirm. Imported projects start as drafts.</p>

      <form className="import-form" onSubmit={onPreview}>
        <div className="mtabs" role="tablist">
          <button type="button" role="tab" aria-selected={kind === "template"} onClick={() => { setKind("template"); setPreview(null); }}><FileSpreadsheet aria-hidden="true" />GEIDA template</button>
          <button type="button" role="tab" aria-selected={kind === "form"} onClick={() => { setKind("form"); setPreview(null); }}><FileUp aria-hidden="true" />Submission form export</button>
        </div>
        <p className="muted small">
          {kind === "template"
            ? <>Fill in the template, one project per row. <a className="text-link" href="/api/projects/import/template/"><Download className="inline-icon" aria-hidden="true" />Download the template</a></>
            : "The Excel export of the Project Data Submission Form (Microsoft Forms). Submitters, links and coordinates are carried over."}
        </p>
        <div className="field-row">
          <label className="dropzone">
            <FileSpreadsheet aria-hidden="true" />
            <span>{file ? file.name : "Excel file (.xlsx)"}</span>
            <input type="file" accept=".xlsx" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); }} />
          </label>
          <label className="dropzone">
            <FileUp aria-hidden="true" />
            <span>{zip ? zip.name : "Boundaries (.zip, optional): one file per project named by code, e.g. AZE1028.kml"}</span>
            <input type="file" accept=".zip" onChange={(e) => { setZip(e.target.files?.[0] ?? null); setPreview(null); }} />
          </label>
        </div>
        <FormAlert text={alert} />
        <button className="btn btn-dark" disabled={busy || !file}>{busy && !preview ? "Checking…" : "Check file"}</button>
      </form>

      {preview && (
        <section className="import-preview">
          <h2>{preview.rows.length} row{preview.rows.length === 1 ? "" : "s"} in {preview.file}</h2>
          {preview.unused_boundaries.length > 0 && <p className="alert alert-warn">Boundary files with no matching project code: {preview.unused_boundaries.join(", ")}.</p>}
          <div className="ptable-wrap">
            <table className="ptable import-table">
              <thead><tr><th>Import</th><th>Row</th><th>Code</th><th>Title</th><th>Country</th><th>Sector / stage</th><th>Action</th><th>Area</th><th>Notes</th></tr></thead>
              <tbody>
                {preview.rows.map((r) => (
                  <tr key={r.row} className={r.action === "error" ? "is-error" : ""}>
                    <td><input type="checkbox" checked={!!keep[r.row]} disabled={r.action === "error"} onChange={(e) => setKeep((k) => ({ ...k, [r.row]: e.target.checked }))} aria-label={`Import row ${r.row}`} /></td>
                    <td>{r.row}</td>
                    <td className="pcode">{r.code}</td>
                    <td>{r.title}{r.source_info?.submitted_by && <span className="psub">From {r.source_info.submitted_by}</span>}</td>
                    <td>{r.country || <span className="muted">?</span>}</td>
                    <td>{label(meta.data?.sectors, r.sector) || "—"} · {r.stage || "—"}</td>
                    <td><span className={`pchip pchip-${r.action}`}>{{ new: "New", update: "Update", error: "Error" }[r.action]}</span></td>
                    <td>
                      {r.boundary === "file" ? <>File: {r.boundary_file}</>
                        : r.suggestion ? <label className="ind-check"><input type="checkbox" checked={!!apply[r.row]} onChange={(e) => setApply((a) => ({ ...a, [r.row]: e.target.checked }))} />{r.suggestion.label}</label>
                        : r.boundary === "link" ? <span className="muted">Link only</span> : <span className="muted">None</span>}
                    </td>
                    <td className="notes">
                      {r.errors.map((x) => <span key={x} className="psub err">{x}</span>)}
                      {r.warnings.map((x) => <span key={x} className="psub warn">{x}</span>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="import-actions">
            <button className="btn btn-dark" onClick={onCommit} disabled={busy || n === 0}>{busy ? "Importing…" : `Import ${n} project${n === 1 ? "" : "s"}`}</button>
            <button className="btn btn-outline" onClick={() => setPreview(null)}>Cancel</button>
          </div>
        </section>
      )}

      {result && (
        <section className="import-preview">
          <h2>Imported: {result.created} new, {result.updated} updated</h2>
          <ul className="plain-list">
            {result.results.map((r) => (
              <li key={r.row}>
                <Link className="text-link" to={`/projects/${r.code}`}>{r.code}</Link> — {r.status}{r.area ? `; ${r.area}` : "; no area yet"}
                {r.errors?.map((e) => <span key={e} className="psub err">{e}</span>)}
              </li>
            ))}
          </ul>
          <Link className="btn btn-dark" to="/projects?tab=mine">See my projects</Link>
        </section>
      )}
    </div></div>
  );
}
