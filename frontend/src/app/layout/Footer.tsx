import { Link } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";
import { forUser, useSite } from "@/shared/lib/site";

export function Footer() {
  const site = useSite();
  const { user } = useAuth();
  return (
    <footer className="site-footer">
      <div className="footer-top">
        <div className="footer-brand">
          <Link to="/" className="footer-logo" aria-label="GEIDA home"><img src="/img/geida-logo.png" alt="GEIDA" /></Link>
          <p>The Islamic Development Bank's geoinformatics data platform, developed with Terra, Expo City Dubai.</p>
        </div>
        <nav className="footer-cols" aria-label="Footer">
          <div>
            <h2>Platform</h2>
            <ul>{forUser(site.data?.primary, user).map((m) => <li key={m.slug}><Link to={`/${m.slug}`}>{m.name}</Link></li>)}</ul>
          </div>
          <div>
            <h2>Knowledge Hub</h2>
            <ul>
              {(site.data?.hub ?? []).map((m) => (
                <li key={m.slug}>
                  {m.url ? <a href={m.url} target="_blank" rel="noopener">{m.name}</a> : <Link to={`/${m.slug}`}>{m.name}</Link>}
                </li>
              ))}
            </ul>
          </div>
          <div>
            <h2>Related</h2>
            <ul>
              <li><a href="https://etoolkit.terrawatch.net/" rel="noopener">EO Toolkit (Phase I)</a></li>
              <li><a href="https://www.isdb.org/" rel="noopener">Islamic Development Bank</a></li>
            </ul>
          </div>
        </nav>
      </div>
      <div className="footer-bottom">
        <a className="footer-powered" href="https://www.expocitydubai.com/" target="_blank" rel="noopener">
          <span>Powered by</span>
          <img src="/img/terra-ecd-logo.png" alt="Terra, Expo City Dubai" />
        </a>
        <span>&copy; {new Date().getFullYear()} Islamic Development Bank</span>
      </div>
    </footer>
  );
}
