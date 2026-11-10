import { LockKeyhole } from "lucide-react";
import { lazy, Suspense, useLayoutEffect } from "react";
import { Link, useLocation } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";
import { useTitle } from "@/shared/lib/dom";
import { forUser, useSite } from "@/shared/lib/site";

// GeoLibre (gis/apps/web) is part of this app; its code loads on the first visit to Analytics.
const GisApp = lazy(() => import("virtual:gis-mount").then((m) => ({ default: m.GisApp })));

/**
 * Analytics: the GIS workspace (GeoLibre, under gis/) below the GEIDA navbar.
 * Its own menu bar (Project, Edit, View, Add Data, Processing...) is the second navbar.
 */
export default function GisWorkspacePage() {
  useTitle("Analytics");
  const { user, loading } = useAuth();
  const site = useSite();
  const { pathname, search } = useLocation();
  // Restricted only when modules.py gives the section roles (off for now: everyone sees it).
  const section = site.data?.primary.find((m) => m.slug === "analytics");
  if (loading || site.isPending) return null;
  if (forUser(section ? [section] : [], user).length === 0) {
    return (
      <div className="section">
        <div className="wrap gis-locked">
          <LockKeyhole aria-hidden="true" />
          <h1>Analytics</h1>
          <p>The Analytics workspace (full GIS toolbox) is for analysts and trainers. Most project work is done with the guided analyses in <Link className="text-link" to="/projects">Projects</Link>.</p>
          {user
            ? <p className="muted">Ask a GEIDA administrator to add you to the “GEIDA analysts” group.</p>
            : <p><Link className="btn btn-dark" to={`/accounts/sign-in?next=${encodeURIComponent(pathname + search)}`}>Sign in</Link></p>}
        </div>
      </div>
    );
  }
  return <Workspace />;
}

function Workspace() {
  // GeoLibre's styles (Tailwind) apply only while <html> has .gis-active; see
  // scripts/postcss-scope-gis.mjs. Undo what the workspace sets on <html> when leaving.
  useLayoutEffect(() => {
    const html = document.documentElement;
    const before = { lang: html.lang, dir: html.dir };
    html.classList.add("gis-active");
    return () => {
      html.classList.remove("gis-active", "dark");
      html.style.colorScheme = "";
      html.lang = before.lang;
      html.dir = before.dir;
    };
  }, []);

  const loadingView = (
    <div className="gis-loading" role="status">
      <span className="tb-spin" aria-hidden="true" />
      Loading the GIS workspace…
    </div>
  );
  return (
    <div className="gis-shell">
      <div className="gis-root">
        <Suspense fallback={loadingView}>
          <GisApp fallback={loadingView} />
        </Suspense>
      </div>
    </div>
  );
}
