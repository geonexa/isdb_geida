import { ArrowUpRight, ChevronDown, Menu, UserRound, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";
import { NamedIcon } from "@/shared/components/icons";
import { useToast } from "@/shared/components/Toasts";
import { forUser, useSite } from "@/shared/lib/site";

export function Logos() {
  return (
    <Link className="mark" to="/" aria-label="GEIDA home">
      <img src="/img/isdb-logo.png" alt="Islamic Development Bank" className="mark-isdb" />
      <span className="mark-rule" aria-hidden="true" />
      <img src="/img/geida-logo.png" alt="GEIDA" className="mark-geida" />
    </Link>
  );
}

type MenuId = "hub" | "account" | null;

export function Navbar() {
  const site = useSite();
  const { user, signOut } = useAuth();
  const toast = useToast();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState<MenuId>(null);
  const [navOpen, setNavOpen] = useState(false);
  const ref = useRef<HTMLElement>(null);

  const active = pathname.split("/")[1] ?? "";
  const hub = site.data?.hub ?? [];
  const hubActive = hub.some((m) => m.slug === active);

  // Close menus on route change, outside click and Escape.
  useEffect(() => { setOpen(null); setNavOpen(false); }, [pathname]);
  useEffect(() => {
    const click = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(null); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(null); };
    document.addEventListener("click", click);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("click", click); document.removeEventListener("keydown", key); };
  }, []);
  const toggle = (id: MenuId) => setOpen((cur) => (cur === id ? null : id));

  async function onSignOut() {
    await signOut();
    toast("You've signed out.", "success");
    navigate("/");
  }

  return (
    <header className="site-header" ref={ref}>
      <Logos />
      <nav className={`primary-nav${navOpen ? " is-open" : ""}`} id="primary-nav" aria-label="Main">
        <ul className="nav-list">
          {forUser(site.data?.primary, user).map((m) => (
            <li key={m.slug}>
              <Link to={`/${m.slug}`} className={`nav-link${active === m.slug ? " is-active" : ""}`} aria-current={active === m.slug ? "page" : undefined}>
                {m.name}
              </Link>
            </li>
          ))}
          <li className="has-menu">
            <button type="button" className={`nav-link${hubActive ? " is-active" : ""}`} aria-expanded={open === "hub"} aria-controls="hub-menu" onClick={() => toggle("hub")}>
              Knowledge Hub<ChevronDown className="chev" aria-hidden="true" />
            </button>
            <div className={`menu menu-hub${open === "hub" ? " is-open" : ""}`} id="hub-menu">
              {hub.map((m) => {
                const body = (
                  <>
                    <NamedIcon name={m.icon} />
                    <span>
                      <span className="menu-title">{m.name}{m.url && <ArrowUpRight className="menu-ext" aria-label="opens in a new tab" />}</span>
                      <span className="menu-desc">{m.summary}</span>
                    </span>
                  </>
                );
                return m.url ? (
                  <a key={m.slug} className="menu-item" href={m.url} target="_blank" rel="noopener">{body}</a>
                ) : (
                  <Link key={m.slug} className={`menu-item${active === m.slug ? " is-active" : ""}`} to={`/${m.slug}`}>{body}</Link>
                );
              })}
            </div>
          </li>
        </ul>
      </nav>

      <div className="nav-actions">
        <div className="has-menu">
          <button type="button" className={`round-btn account${user ? " is-in" : ""}`} aria-expanded={open === "account"} aria-controls="account-menu" aria-label="Account menu" onClick={() => toggle("account")}>
            {user ? <span className="initial">{user.username.charAt(0).toUpperCase()}</span> : <UserRound aria-hidden="true" />}
          </button>
          <div className={`menu menu-account${open === "account" ? " is-open" : ""}`} id="account-menu">
            {user ? (
              <>
                <p className="menu-user">{user.full_name}<span>{user.email}</span></p>
                {user.is_staff && <a className="menu-item" href="/admin/">Administration</a>}
                <button className="menu-item menu-logout" type="button" onClick={onSignOut}>Sign out</button>
              </>
            ) : (
              <>
                <Link className="menu-item" to={`/accounts/sign-in?next=${encodeURIComponent(pathname)}`}>Sign in</Link>
                <Link className="menu-item" to="/accounts/register">Create account</Link>
              </>
            )}
          </div>
        </div>
        <button type="button" className="round-btn nav-toggle" aria-expanded={navOpen} aria-controls="primary-nav" aria-label={navOpen ? "Close menu" : "Open menu"} onClick={() => setNavOpen((v) => !v)}>
          <Menu className="when-closed" aria-hidden="true" />
          <X className="when-open" aria-hidden="true" />
        </button>
      </div>
    </header>
  );
}
