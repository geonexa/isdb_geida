import { Check, ChevronLeft, CircleAlert } from "lucide-react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";
import { useBodyClass, useTitle } from "@/shared/lib/dom";
import { STEP_NAMES, StatusChip, useMeta, useProject } from "@/features/projects/data";
import { StepArea } from "@/features/projects/steps/StepArea";
import { StepDocuments } from "@/features/projects/steps/StepDocuments";
import { StepIdentity } from "@/features/projects/steps/StepIdentity";
import { StepResults } from "@/features/projects/steps/StepResults";
import { StepThemes } from "@/features/projects/steps/StepThemes";
import type { Project } from "@/features/projects/types";

/** Which steps are complete (✓) or have a problem (!) for the step bar. */
function stepState(p: Project | undefined, i: number): "done" | "warn" | "" {
  if (!p) return "";
  switch (i) {
    case 1: return p.title && p.country_iso3 && p.sector && p.stage ? "done" : "warn";
    case 2: return p.area ? (p.area.notes.some((n) => /outside|Only/.test(n)) ? "warn" : "done") : "";
    case 3: return p.themes.length || p.components.length ? "done" : "";
    case 4: return p.indicators.length ? (p.indicators.some((x) => x.warnings?.some((w) => /converting/.test(w))) ? "warn" : "done") : "";
    case 5: return p.documents.length ? "done" : "";
    default: return "";
  }
}

export default function ProjectWizard() {
  const { code } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const { user, loading } = useAuth();
  const meta = useMeta();
  const project = useProject(code);
  useBodyClass("page-map");
  useTitle(code ? `Edit ${code}` : "New project");

  const step = code ? Math.min(5, Math.max(1, Number(params.get("step") ?? 1) || 1)) : 1;
  const go = (n: number) => setParams({ step: String(n) }, { replace: false });

  if (!loading && !user) return <Navigate to={`/accounts/sign-in?next=${encodeURIComponent(location.pathname + location.search)}`} replace />;
  if (code && project.isError) {
    return <div className="section"><div className="wrap"><h1>Project not found</h1><p><Link className="text-link" to="/projects">Back to projects</Link></p></div></div>;
  }
  const p = project.data;
  if (p && !p.permissions.can_edit) {
    return (
      <div className="section"><div className="wrap">
        <h1>{p.code} can't be edited</h1>
        <p className="muted">{p.status === "review" ? "It's under review. A reviewer has to return it before it can be changed." : "You don't have permission to edit this project."}</p>
        <Link className="btn btn-dark" to={`/projects/${p.code}`}>Open the project</Link>
      </div></div>
    );
  }
  const ready = meta.data && (!code || p);

  return (
    <div className="wizard">
      <header className="wizard-head">
        <Link className="back-link" to={p ? `/projects/${p.code}` : "/projects"}><ChevronLeft aria-hidden="true" />{p ? p.code : "Projects"}</Link>
        <div className="wizard-title">
          <h1>{p ? p.title : "New project"}</h1>
          {p && <StatusChip status={p.status} />}
        </div>
        <ol className="stepper">
          {STEP_NAMES.map((name, i) => {
            const n = i + 1;
            const st = stepState(p, n);
            return (
              <li key={name}>
                <button type="button" disabled={!code} aria-current={n === step ? "step" : undefined}
                        className={`step${n === step ? " is-current" : ""}${st ? ` is-${st}` : ""}`} onClick={() => go(n)}>
                  <span className="step-n">{st === "done" ? <Check aria-hidden="true" /> : st === "warn" ? <CircleAlert aria-hidden="true" /> : n}</span>
                  {name}
                </button>
              </li>
            );
          })}
        </ol>
      </header>
      {p?.review_comment && p.status === "draft" && (
        <div className="alert alert-warn wizard-alert" role="note"><CircleAlert aria-hidden="true" /><div><strong>Returned by reviewer:</strong> {p.review_comment}</div></div>
      )}
      {!ready ? (
        <p className="muted wizard-loading">Loading…</p>
      ) : step === 1 ? (
        <StepIdentity meta={meta.data!} project={p} onDone={(saved, created) => created ? navigate(`/projects/${saved.code}/edit?step=2`) : go(2)} />
      ) : step === 2 ? (
        <StepArea meta={meta.data!} project={p!} onBack={() => go(1)} onNext={() => go(3)} />
      ) : step === 3 ? (
        <StepThemes meta={meta.data!} project={p!} onBack={() => go(2)} onNext={() => go(4)} />
      ) : step === 4 ? (
        <StepResults meta={meta.data!} project={p!} onBack={() => go(3)} onNext={() => go(5)} />
      ) : (
        <StepDocuments meta={meta.data!} project={p!} onBack={() => go(4)} onEdit={go} />
      )}
    </div>
  );
}
