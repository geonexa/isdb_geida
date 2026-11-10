import { ChevronLeft } from "lucide-react";
import { useEffect } from "react";
import { Link, useParams } from "react-router-dom";

import { NamedIcon } from "@/shared/components/icons";
import { useTitle } from "@/shared/lib/dom";
import { useSite } from "@/shared/lib/site";
import NotFound from "@/features/site/NotFound";

/** Placeholder page for a section that is still being built (Analytics, Dashboards...). */
export default function ModulePage() {
  const { slug } = useParams();
  const site = useSite();
  const module = [...(site.data?.primary ?? []), ...(site.data?.hub ?? [])].find((m) => m.slug === slug);
  useTitle(module?.name);
  useEffect(() => {
    if (module?.url) window.location.replace(module.url); // hosted elsewhere, e.g. the GEIDA LMS
  }, [module]);

  if (site.isPending || module?.url) return null;
  if (!module) return <NotFound />;
  return (
    <>
      <section className="page-head">
        <div className="wrap">
          <Link className="back-link" to="/"><ChevronLeft aria-hidden="true" />Home</Link>
          <div className="page-title">
            <span className="page-icon"><NamedIcon name={module.icon} /></span>
            <div>
              <h1>{module.name}</h1>
              <p>{module.summary}</p>
            </div>
          </div>
        </div>
      </section>
      <section className="section">
        <div className="wrap placeholder">
          <div className="status"><span className="status-dot" aria-hidden="true" />In development for GEIDA Phase II</div>
          {module.features.length ? (
            <>
              <h2>What this section will do</h2>
              <ul className="check-list">{module.features.map((f) => <li key={f}>{f}</li>)}</ul>
            </>
          ) : (
            <p className="muted">Content for this section is being prepared.</p>
          )}
        </div>
      </section>
    </>
  );
}
