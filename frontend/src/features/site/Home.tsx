import { ArrowLeft, ArrowRight, Check, ChevronRight, ImageOff, RefreshCw } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";

import { NamedIcon } from "@/shared/components/icons";
import { useBodyClass, useTitle } from "@/shared/lib/dom";
import { useAuth } from "@/features/auth/AuthContext";
import { forUser, useSite } from "@/shared/lib/site";

export default function Home() {
  useTitle("Home");
  useBodyClass("page-home");
  const site = useSite();
  const { user } = useAuth();
  const [stage, setStage] = useState("pcn");
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const cycle = site.data?.cycle ?? [];
  const active = Math.max(0, cycle.findIndex((c) => c.key === stage));
  const current = cycle[active];
  // On narrow screens the stage rail scrolls sideways: keep the chosen stage in view.
  useEffect(() => {
    const btn = tabs.current[active];
    const rail = btn?.closest("ol");
    if (btn && rail && rail.scrollWidth > rail.clientWidth) {
      const li = btn.parentElement as HTMLElement;
      rail.scrollTo({ left: li.offsetLeft - (rail.clientWidth - li.clientWidth) / 2, behavior: "smooth" });
    }
  }, [active]);

  function tabKey(e: KeyboardEvent, i: number) {
    const n = cycle.length;
    const next = { ArrowRight: (i + 1) % n, ArrowLeft: (i - 1 + n) % n, Home: 0, End: n - 1 }[e.key];
    if (next === undefined) return;
    e.preventDefault();
    setStage(cycle[next].key);
    tabs.current[next]?.focus();
  }

  return (
    <>
      <section className="hero" style={{ "--hero-img": "url('/img/hero.jpg')" } as React.CSSProperties}>
        <div className="hero-grid">
          <div className="hero-copy">
            <h1>
              <span className="h1-main">GEIDA</span><span className="visually-hidden">: </span>
              <span className="h1-sub">IsDB Geoinformatics Data Platform</span>
            </h1>
            <p className="hero-tagline">Earth observation for every stage of an IsDB project</p>
            <div className="hero-actions">
              <Link className="btn btn-light" to="/projects">Explore projects</Link>
              <a className="btn btn-ghost" href="#project-cycle">See the project lifecycle</a>
            </div>
          </div>
        </div>
      </section>

      <section className="section components" aria-labelledby="comp-h">
        <div className="wrap">
          <div className="section-head">
            <h2 id="comp-h">Three components, one objective</h2>
            <p>Evidence-based project design and monitoring across the Bank, delivered through technology, action in real projects, and certified people.</p>
          </div>
          <div className="comp-grid">
            {(site.data?.components ?? []).map((c) => (
              <article className="comp-card" key={c.key}>
                <div className="comp-thumb">
                  <img src={c.image} alt="" loading="lazy" />
                  <span className="comp-chip">Component {c.key}</span>
                </div>
                <div className="comp-body">
                  <h3>{c.name}</h3>
                  <p className="comp-title">{c.title}</p>
                  <p>{c.text}</p>
                  <ul className="comp-items">{c.items.map((i) => <li key={i}>{i}</li>)}</ul>
                </div>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="section lifecycle" id="project-cycle" aria-labelledby="cycle-h">
        <div className="wrap">
          <div className="section-head lc-head">
            <p className="eyebrow">Project lifecycle</p>
            <h2 id="cycle-h">From first idea to lasting impact</h2>
            <p>GEIDA follows an IsDB project through all six stages of the project cycle. At each one, Earth observation answers the question that stage asks, and the evidence stays with the project.</p>
          </div>

          <ol className="lc-rail" role="tablist" aria-label="Project lifecycle stages">
            {cycle.map((c, i) => (
              <li key={c.key} className={i < active ? "is-past" : ""}>
                <button ref={(el) => { tabs.current[i] = el; }} type="button" role="tab" className="lc-step"
                  id={`tab-${c.key}`} aria-controls="lc-panel" aria-selected={stage === c.key} tabIndex={stage === c.key ? 0 : -1}
                  onClick={() => setStage(c.key)} onKeyDown={(e) => tabKey(e, i)}>
                  <span className="lc-dot">{i < active ? <Check aria-hidden="true" /> : i + 1}</span>
                  <span className="lc-inst">{c.instrument}</span>
                  <span className="lc-name">{c.stage}</span>
                </button>
              </li>
            ))}
          </ol>

          {current && (
            <div className="lc-panel" id="lc-panel" role="tabpanel" aria-labelledby={`tab-${current.key}`}>
              <figure className="lc-figure">
                <StageImage key={current.key} src={current.image} alt={current.alt} />
                <figcaption>
                  <span className="lc-chip">Stage {active + 1} of {cycle.length} · {current.instrument}</span>
                  <span className="lc-question">{current.question}</span>
                </figcaption>
              </figure>
              <div className="lc-body">
                <h3>{current.stage}</h3>
                <p className="lc-sub">In GEIDA: the project's <strong>{current.phase}</strong> workspace</p>
                <p className="panel-label">What GEIDA provides</p>
                <ul className="check-list">{current.outputs.map((o) => <li key={o}>{o}</li>)}</ul>
                <p className="panel-label">Why it matters</p>
                <p className="panel-value">{current.value}</p>
                <div className="lc-nav">
                  <button type="button" className="icon-btn" aria-label="Previous stage" disabled={active === 0} onClick={() => setStage(cycle[active - 1].key)}><ArrowLeft aria-hidden="true" /></button>
                  <button type="button" className="icon-btn" aria-label="Next stage" disabled={active === cycle.length - 1} onClick={() => setStage(cycle[active + 1].key)}><ArrowRight aria-hidden="true" /></button>
                  {active === cycle.length - 1
                    ? <span className="lc-loop"><RefreshCw aria-hidden="true" />Lessons feed the next project's identification</span>
                    : <span className="lc-next">Next: {cycle[active + 1].stage}</span>}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="section modules" aria-labelledby="modules-h">
        <div className="wrap modules-grid">
          <div className="modules-intro">
            <h2 id="modules-h">One platform, from data to decision</h2>
            <p>GEIDA turns the EO Toolkit's library into tools staff use in their daily work. Every map, number and report traces back to its source data.</p>
            <Link className="text-link" to="/geoportal">Browse the Data Catalog</Link>
          </div>
          <ul className="module-list">
            {forUser(site.data?.primary, user).map((m) => (
              <li key={m.slug}>
                <Link className="module-row" to={`/${m.slug}`}>
                  <span className="module-icon"><NamedIcon name={m.icon} /></span>
                  <span className="module-text">
                    <span className="module-name">{m.name}</span>
                    <span className="module-sum">{m.summary}</span>
                  </span>
                  <ChevronRight className="module-go" aria-hidden="true" />
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </section>

    </>
  );
}

/** Stage photo; a calm teal panel stands in until the image file exists. */
function StageImage({ src, alt }: { src: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return <div className="lc-img lc-img-missing" role="img" aria-label={alt}><ImageOff aria-hidden="true" /></div>;
  }
  return <img className="lc-img" src={src} alt={alt} onError={() => setFailed(true)} />;
}
