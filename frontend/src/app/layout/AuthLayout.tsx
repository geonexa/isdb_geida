import { ChevronLeft } from "lucide-react";
import { Link, Outlet } from "react-router-dom";

import { Logos } from "@/app/layout/Navbar";
import { useBodyClass } from "@/shared/lib/dom";

export function AuthLayout() {
  useBodyClass("page-auth");
  return (
    <main id="main">
      <div className="auth">
        <aside className="auth-visual" style={{ "--hero-img": "url('/img/hero.jpg')" } as React.CSSProperties} aria-hidden="true">
          <div className="auth-visual-inner">
            <p className="auth-brand"><span>GEIDA</span>IsDB Geoinformatics Data Platform</p>
            <p className="auth-quote">Earth observation for every stage of an IsDB project</p>
          </div>
        </aside>
        <div className="auth-main">
          <div className="auth-top">
            <Logos />
            <Link className="back-link" to="/"><ChevronLeft aria-hidden="true" />Back to home</Link>
          </div>
          <div className="auth-card">
            <Outlet />
          </div>
          <p className="auth-foot">&copy; {new Date().getFullYear()} Islamic Development Bank. Need help? Contact the GEIDA team.</p>
        </div>
      </div>
    </main>
  );
}
