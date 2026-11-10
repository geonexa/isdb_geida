import { useQuery } from "@tanstack/react-query";
import type { FeatureCollection } from "geojson";
import { FileUp, FolderKanban, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import { api } from "@/shared/api/client";
import { useAuth } from "@/features/auth/AuthContext";
import { useTitle } from "@/shared/lib/dom";
import { label, StatusChip, useMeta } from "@/features/projects/data";
import { ProjectMap } from "@/features/projects/ProjectMap";
import type { BBox, ProjectItem } from "@/features/projects/types";

type Tab = "all" | "mine" | "review";

export default function ProjectListPage({ tab: initialTab = "all" }: { tab?: Tab }) {
  useTitle("Projects");
  const { user } = useAuth();
  const meta = useMeta();
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const [tab, setTab] = useState<Tab>((search.get("tab") as Tab) || initialTab);
  const [q, setQ] = useState("");
  const [country, setCountry] = useState("");
  const [sector, setSector] = useState("");
  const [stage, setStage] = useState("");
  const [status, setStatus] = useState("");

  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (country) params.set("country", country);
  if (sector) params.set("sector", sector);
  if (stage) params.set("stage", stage);
  if (tab === "review") params.set("status", "review");
  else if (status) params.set("status", status);
  if (tab === "mine") params.set("mine", "1");

  const list = useQuery({
    queryKey: ["projects", params.toString(), user?.id],
    queryFn: () => api<{ projects: ProjectItem[]; counts: Record<string, number>; truncated: boolean }>(`/api/projects/?${params}`),
  });
  const projects = list.data?.projects ?? [];
  const reviewer = !!user?.is_reviewer;

  const points = useMemo<FeatureCollection>(() => ({
    type: "FeatureCollection",
    features: projects.filter((p) => p.area).map((p) => ({
      type: "Feature",
      properties: { code: p.code, status: p.status },
      geometry: { type: "Point", coordinates: p.area!.centroid },
    })),
  }), [projects]);
  const fit = useMemo<BBox | null>(() => {
    const c = meta.data?.countries.find((x) => x.iso3 === country);
    if (c) return c.bbox;
    const boxes = projects.filter((p) => p.area).map((p) => p.area!.bbox);
    if (!boxes.length) return null;
    return [Math.min(...boxes.map((b) => b[0])), Math.min(...boxes.map((b) => b[1])),
            Math.max(...boxes.map((b) => b[2])), Math.max(...boxes.map((b) => b[3]))];
  }, [country, meta.data, projects]);

  return (
    <div className="plist">
      <section className="plist-main">
        <header className="plist-head">
          <div>
            <h1><FolderKanban aria-hidden="true" />Projects</h1>
            <p className="muted">IsDB projects onboarded to GEIDA: area of influence, Results Framework and CRI indicators.</p>
          </div>
          {user && (
            <div className="plist-actions">
              <Link className="btn btn-outline" to="/projects/import"><FileUp aria-hidden="true" />Import</Link>
              <Link className="btn btn-dark" to="/projects/new"><Plus aria-hidden="true" />New project</Link>
            </div>
          )}
        </header>

        <div className="ptabs" role="tablist">
          <button role="tab" aria-selected={tab === "all"} onClick={() => setTab("all")}>All projects</button>
          {user && <button role="tab" aria-selected={tab === "mine"} onClick={() => setTab("mine")}>My projects</button>}
          {reviewer && (
            <button role="tab" aria-selected={tab === "review"} onClick={() => setTab("review")}>
              Review queue{list.data?.counts.review ? <span className="pcount">{list.data.counts.review}</span> : null}
            </button>
          )}
        </div>

        <div className="pfilters">
          <label className="psearch"><Search aria-hidden="true" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search code, title or country" aria-label="Search projects" /></label>
          <select className="input" value={country} onChange={(e) => setCountry(e.target.value)} aria-label="Country">
            <option value="">All countries</option>
            {meta.data?.countries.map((c) => <option key={c.iso3} value={c.iso3}>{c.name}</option>)}
          </select>
          <select className="input" value={sector} onChange={(e) => setSector(e.target.value)} aria-label="Sector">
            <option value="">All sectors</option>
            {meta.data?.sectors.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
          <select className="input" value={stage} onChange={(e) => setStage(e.target.value)} aria-label="Stage">
            <option value="">All stages</option>
            {meta.data?.stages.map((o) => <option key={o.value} value={o.value}>{o.value}</option>)}
          </select>
          {tab !== "review" && user && (
            <select className="input" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">
              <option value="">Any status</option>
              {meta.data?.statuses.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          )}
        </div>

        <div className="ptable-wrap">
          {list.isPending ? (
            <p className="muted pempty">Loading projects…</p>
          ) : projects.length === 0 ? (
            <div className="pempty">
              <p>No projects match.</p>
              {user ? <p className="muted">Add one with <Link className="text-link" to="/projects/new">New project</Link> or import several from a spreadsheet.</p>
                : <p className="muted"><Link className="text-link" to="/accounts/sign-in?next=/projects">Sign in</Link> to add projects and see your drafts.</p>}
            </div>
          ) : (
            <table className="ptable">
              <thead>
                <tr><th>Code</th><th>Title</th><th>Country</th><th>Sector</th><th>Stage</th><th>Area</th><th>Status</th></tr>
              </thead>
              <tbody>
                {projects.map((p) => (
                  <tr key={p.code} onClick={() => navigate(`/projects/${p.code}`)} tabIndex={0}
                      onKeyDown={(e) => { if (e.key === "Enter") navigate(`/projects/${p.code}`); }}>
                    <td className="pcode">{p.code}</td>
                    <td>{p.title}<span className="psub">{p.source !== "manual" ? `From ${p.source === "form" ? "submission form" : "import"} · ` : ""}{p.owner}</span></td>
                    <td>{p.country_name}</td>
                    <td>{label(meta.data?.sectors, p.sector)}</td>
                    <td>{p.stage}</td>
                    <td className="nowrap">{p.area ? `${Math.round(p.area.area_km2).toLocaleString()} km²` : <span className="muted">—</span>}</td>
                    <td><StatusChip status={p.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
      <aside className="plist-map">
        <ProjectMap points={points} fitBbox={fit} onPointClick={(code) => navigate(`/projects/${code}`)} />
        <div className="plegend"><span className="dot published" />Published<span className="dot review" />Under review<span className="dot draft" />Draft</div>
      </aside>
    </div>
  );
}
