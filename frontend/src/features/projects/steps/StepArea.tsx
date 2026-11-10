import type { FeatureCollection } from "geojson";
import { CircleAlert, CircleCheck, FileUp, Globe2, MapPin, Map as MapIcon, PenLine, Trash2, Undo2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api, ApiError, upload } from "@/shared/api/client";
import { FormAlert } from "@/shared/components/Field";
import { useConfirm } from "@/shared/components/Confirm";
import { useToast } from "@/shared/components/Toasts";
import { km2, label, useSetProject } from "@/features/projects/data";
import { ProjectMap } from "@/features/projects/ProjectMap";
import type { AreaPreview, Meta, Project } from "@/features/projects/types";

type Method = "upload" | "draw" | "admin" | "buffer" | "country";
type Props = { meta: Meta; project: Project; onBack: () => void; onNext: () => void };
type Unit = { gid: string; name: string; level: number; type: string; parent_gid: string; path: string };

const TABS: { id: Method; label: string; icon: typeof FileUp }[] = [
  { id: "upload", label: "Upload", icon: FileUp },
  { id: "draw", label: "Draw", icon: PenLine },
  { id: "admin", label: "Admin units", icon: MapIcon },
  { id: "buffer", label: "Point + buffer", icon: MapPin },
  { id: "country", label: "Whole country", icon: Globe2 },
];

export function StepArea({ meta, project, onBack, onNext }: Props) {
  const toast = useToast();
  const confirm = useConfirm();
  const setProject = useSetProject();
  const country = meta.countries.find((c) => c.iso3 === project.country_iso3);
  const [method, setMethod] = useState<Method>((project.area?.method as Method) ?? "upload");
  const [preview, setPreview] = useState<AreaPreview | null>(null);
  const [alert, setAlert] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Inputs per method
  const [file, setFile] = useState<File | null>(null);
  const [picked, setPicked] = useState<number[] | null>(null);
  const [coords, setCoords] = useState<[number, number][]>([]);
  const [pt, setPt] = useState<{ lon: string; lat: string; km: string }>({
    lon: project.area?.buffer.lon?.toString() ?? "", lat: project.area?.buffer.lat?.toString() ?? "", km: project.area?.buffer.km?.toString() ?? "5",
  });
  const [level, setLevel] = useState(1);
  const [parent, setParent] = useState("");
  const [units, setUnits] = useState<FeatureCollection | null>(null);
  const [parents, setParents] = useState<Unit[]>([]);
  const [gids, setGids] = useState<string[]>(project.area?.method === "admin" ? project.area.admin_gids : []);
  const [unitFilter, setUnitFilter] = useState("");
  const [unitsMsg, setUnitsMsg] = useState<string | null>(null);

  useEffect(() => { setPreview(null); setAlert(null); }, [method]);

  // Admin units for the picker (display geometry).
  useEffect(() => {
    if (method !== "admin") return;
    const q = new URLSearchParams({ iso3: project.country_iso3, level: String(level) });
    if (parent && level > 1) q.set("parent", parent);
    setUnitsMsg("Loading boundaries…");
    api<FeatureCollection>(`/api/boundaries/units/geojson/?${q}`)
      .then((d) => { setUnits(d); setUnitsMsg(d.features.length ? null : "No units at this level for this country. Try a higher level."); })
      .catch((e) => { setUnits(null); setUnitsMsg(e instanceof ApiError ? e.message : "Couldn't load boundaries."); });
  }, [method, level, parent, project.country_iso3]);
  useEffect(() => {
    if (method !== "admin" || level < 2) { setParents([]); return; }
    api<{ units: Unit[] }>(`/api/boundaries/units/?iso3=${project.country_iso3}&level=${level - 1}`)
      .then((d) => setParents(d.units)).catch(() => setParents([]));
  }, [method, level, project.country_iso3]);

  const unitList = useMemo(() => (units?.features ?? [])
    .map((f) => f.properties as Unit)
    .filter((u) => !unitFilter || u.name.toLowerCase().includes(unitFilter.toLowerCase()))
    .sort((a, b) => a.name.localeCompare(b.name)), [units, unitFilter]);
  const toggleUnit = (gid: string) => setGids((g) => (g.includes(gid) ? g.filter((x) => x !== gid) : [...g, gid]));

  function request(save: boolean): Promise<AreaPreview | { project: Project }> {
    const url = save ? `/api/projects/${project.code}/area/` : "/api/projects/area/preview/";
    if (method === "upload") {
      if (!file) throw new Error("Choose a file to upload.");
      const form = new FormData();
      form.append("file", file);
      form.append("country_iso3", project.country_iso3);
      if (picked) form.append("features", picked.join(","));
      return upload(url, form);
    }
    const body: Record<string, unknown> = { method, country_iso3: project.country_iso3 };
    if (method === "draw") {
      if (coords.length < 3) throw new Error("Click at least three points on the map.");
      body.geometry = { type: "Polygon", coordinates: [[...coords, coords[0]]] };
    } else if (method === "buffer") {
      Object.assign(body, { lon: pt.lon, lat: pt.lat, km: pt.km });
    } else if (method === "admin") {
      if (!gids.length) throw new Error("Pick at least one unit on the map or in the list.");
      body.gids = gids;
    }
    return api(url, { method: "POST", body });
  }

  async function check() {
    setBusy(true); setAlert(null);
    try {
      const res = (await request(false)) as AreaPreview;
      setPreview(res);
      if (res.features && !picked) setPicked(res.features.filter((f) => f.selected).map((f) => f.index));
    } catch (e) {
      setPreview(null);
      setAlert(e instanceof Error ? e.message : "Couldn't check the area.");
    } finally { setBusy(false); }
  }

  async function save() {
    setBusy(true); setAlert(null);
    try {
      const res = (await request(true)) as { project: Project };
      setProject(res.project);
      setPreview(null);
      toast(`Area saved: ${km2(res.project.area!.area_km2)}.`, "success");
    } catch (e) {
      setAlert(e instanceof Error ? e.message : "Couldn't save the area.");
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!(await confirm({ title: "Remove the saved area of influence?", message: "Analyses and satellite data need an area; you can draw or upload a new one afterwards.", confirmLabel: "Remove area", tone: "danger" }))) return;
    const res = await api<{ project: Project }>(`/api/projects/${project.code}/area/`, { method: "DELETE" });
    setProject(res.project);
  }

  const onMapClick = (ll: [number, number]) => {
    if (method === "draw") { setCoords((c) => [...c, ll]); setPreview(null); }
    if (method === "buffer") { setPt((s) => ({ ...s, lon: ll[0].toFixed(6), lat: ll[1].toFixed(6) })); setPreview(null); }
  };
  const saved = project.area;
  const fit = preview?.bbox ?? saved?.bbox ?? country?.bbox ?? null;
  const warn = (n: string) => /outside|Only|Repaired|Ignored|no coordinate/.test(n);

  return (
    <div className="wizard-body">
      <div className="wizard-panel">
        <h2>Country and area of influence</h2>
        <p className="muted">Where the project works in {project.country_name}. Analyses and indicators use this area.</p>

        {saved && !preview && (
          <div className="area-card is-saved">
            <div className="area-card-head">
              <CircleCheck aria-hidden="true" />
              <div><strong>{km2(saved.area_km2)}</strong><span>{label(meta.area_methods, saved.method)}{saved.source_name ? ` · ${saved.source_name}` : ""}</span></div>
              <button type="button" className="icon-btn" onClick={remove} aria-label="Remove area"><Trash2 aria-hidden="true" /></button>
            </div>
            {saved.notes.length > 0 && <ul className="area-notes">{saved.notes.map((n) => <li key={n} className={warn(n) ? "is-warn" : ""}>{n}</li>)}</ul>}
            <p className="muted small">To replace it, use one of the options below.</p>
          </div>
        )}

        <div className="mtabs" role="tablist">
          {TABS.map(({ id, label: l, icon: Icon }) => (
            <button key={id} role="tab" aria-selected={method === id} onClick={() => setMethod(id)}><Icon aria-hidden="true" />{l}</button>
          ))}
        </div>

        <div className="mtab-body">
          {method === "upload" && (
            <>
              <label className="dropzone">
                <FileUp aria-hidden="true" />
                <span>{file ? file.name : "Choose a GeoJSON, KML/KMZ, GeoPackage or zipped shapefile"}</span>
                <input type="file" accept=".geojson,.json,.kml,.kmz,.gpkg,.zip" onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPicked(null); setPreview(null); }} />
              </label>
              {preview?.features && preview.features.length > 1 && (
                <fieldset className="feature-pick">
                  <legend>Features in the file</legend>
                  {preview.features.map((f) => (
                    <label key={f.index} className={f.whole_world ? "is-off" : ""}>
                      <input type="checkbox" disabled={!/Polygon/.test(f.geom_type)} checked={!!picked?.includes(f.index)}
                             onChange={() => setPicked((p) => (p?.includes(f.index) ? p.filter((x) => x !== f.index) : [...(p ?? []), f.index]))} />
                      {f.name} <span className="muted">({f.geom_type}{f.whole_world ? ", whole world" : ""})</span>
                    </label>
                  ))}
                  <button type="button" className="btn btn-outline btn-sm" onClick={check}>Update with selection</button>
                </fieldset>
              )}
            </>
          )}
          {method === "draw" && (
            <div className="draw-tools">
              <p className="muted">Click on the map to add corners. {coords.length} point{coords.length === 1 ? "" : "s"}.</p>
              <button type="button" className="btn btn-outline btn-sm" disabled={!coords.length} onClick={() => { setCoords((c) => c.slice(0, -1)); setPreview(null); }}><Undo2 aria-hidden="true" />Undo</button>
              <button type="button" className="btn btn-outline btn-sm" disabled={!coords.length} onClick={() => { setCoords([]); setPreview(null); }}>Clear</button>
            </div>
          )}
          {method === "admin" && (
            <div className="admin-pick">
              <div className="field-row">
                <div className="field">
                  <label htmlFor="adm-level">Level</label>
                  <select id="adm-level" className="input" value={level} onChange={(e) => { setLevel(Number(e.target.value)); setParent(""); }}>
                    <option value={1}>Level 1 (province / region)</option>
                    <option value={2}>Level 2 (district)</option>
                    <option value={3}>Level 3 (sub-district)</option>
                  </select>
                </div>
                {level > 1 && (
                  <div className="field">
                    <label htmlFor="adm-parent">Within</label>
                    <select id="adm-parent" className="input" value={parent} onChange={(e) => setParent(e.target.value)}>
                      <option value="">All of {project.country_name}</option>
                      {parents.map((u) => <option key={u.gid} value={u.gid}>{u.name}</option>)}
                    </select>
                  </div>
                )}
              </div>
              {unitsMsg && <p className="muted small">{unitsMsg}</p>}
              {unitList.length > 0 && (
                <>
                  <input className="input" placeholder="Filter by name" value={unitFilter} onChange={(e) => setUnitFilter(e.target.value)} aria-label="Filter units" />
                  <ul className="unit-list">
                    {unitList.map((u) => (
                      <li key={u.gid}><label><input type="checkbox" checked={gids.includes(u.gid)} onChange={() => toggleUnit(u.gid)} />{u.name}<span className="muted">{u.type}</span></label></li>
                    ))}
                  </ul>
                </>
              )}
              <p className="small">{gids.length} selected{gids.length > 0 && <> · <button type="button" className="link-btn" onClick={() => setGids([])}>clear</button></>}</p>
            </div>
          )}
          {method === "buffer" && (
            <div className="field-row three">
              <div className="field"><label htmlFor="b-lat">Latitude</label><input id="b-lat" className="input" inputMode="decimal" value={pt.lat} onChange={(e) => setPt({ ...pt, lat: e.target.value })} placeholder="9.6373" /></div>
              <div className="field"><label htmlFor="b-lon">Longitude</label><input id="b-lon" className="input" inputMode="decimal" value={pt.lon} onChange={(e) => setPt({ ...pt, lon: e.target.value })} placeholder="6.3887" /></div>
              <div className="field"><label htmlFor="b-km">Radius (km)</label><input id="b-km" className="input" inputMode="decimal" value={pt.km} onChange={(e) => setPt({ ...pt, km: e.target.value })} /></div>
              <p className="muted small span-all">Or click the map to place the point.</p>
            </div>
          )}
          {method === "country" && <p className="muted">Use the whole of {project.country_name} (GADM boundary). Suits country-wide programmes such as lines of finance.</p>}

          <div className="mtab-actions">
            <button type="button" className="btn btn-outline" onClick={check} disabled={busy}>{busy && !preview ? "Checking…" : "Check area"}</button>
          </div>
        </div>

        <FormAlert text={alert} />
        {preview && (
          <div className="area-card is-preview">
            <div className="area-card-head">
              {preview.notes.some(warn) ? <CircleAlert aria-hidden="true" /> : <CircleCheck aria-hidden="true" />}
              <div><strong>{km2(preview.area_km2)}</strong><span>{preview.parts} polygon{preview.parts === 1 ? "" : "s"}{preview.inside_country != null ? ` · ${Math.round(preview.inside_country * 100)}% inside ${project.country_name}` : ""}</span></div>
            </div>
            {preview.notes.length > 0 && <ul className="area-notes">{preview.notes.map((n) => <li key={n} className={warn(n) ? "is-warn" : ""}>{n}</li>)}</ul>}
            <div className="area-card-actions">
              <button type="button" className="btn btn-dark" onClick={save} disabled={busy}>{busy ? "Saving…" : saved ? "Replace saved area" : "Use this area"}</button>
              <button type="button" className="btn btn-outline" onClick={() => setPreview(null)}>Discard</button>
            </div>
          </div>
        )}

        <div className="wizard-foot">
          <button type="button" className="btn btn-outline" onClick={onBack}>Back</button>
          <button type="button" className="btn btn-dark" onClick={onNext}>{saved ? "Continue" : "Skip for now"}</button>
        </div>
      </div>
      <ProjectMap className="wizard-map" fitBbox={fit} area={saved?.geometry ?? null} preview={preview?.geometry ?? null}
                  units={method === "admin" ? units : null} selectedUnits={gids} onUnitClick={method === "admin" ? toggleUnit : undefined}
                  drawCoords={method === "draw" ? coords : []} marker={method === "buffer" && pt.lat && pt.lon ? [Number(pt.lon), Number(pt.lat)] : null}
                  onMapClick={onMapClick} cursor={method === "draw" || method === "buffer" ? "crosshair" : ""} />
    </div>
  );
}
