import { Link } from "react-router-dom";

import { NamedIcon } from "@/shared/components/icons";
import { useTitle } from "@/shared/lib/dom";
import { useSite } from "@/shared/lib/site";

export default function NotFound() {
  useTitle("Page not found");
  const site = useSite();
  return (
    <section className="nf">
      <div className="nf-copy">
        <p className="nf-code">Error 404</p>
        <h1>Page not found</h1>
        <p className="nf-lead">The link may be old, or the page may have moved. Try one of these instead.</p>
        <div className="nf-actions">
          <Link className="btn btn-dark" to="/">Go to home</Link>
          <Link className="btn btn-outline" to="/geoportal">Open Data Catalog</Link>
        </div>
        <ul className="nf-links">
          {(site.data?.primary ?? []).map((m) => (
            <li key={m.slug}><Link to={`/${m.slug}`}><NamedIcon name={m.icon} />{m.name}</Link></li>
          ))}
        </ul>
      </div>
    </section>
  );
}
