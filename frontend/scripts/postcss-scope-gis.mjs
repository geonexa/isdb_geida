// PostCSS plugin: GeoLibre's styles apply only while the Analytics workspace is
// on screen (<html class="gis-active">, set by src/features/gis/GisWorkspacePage.tsx).
//
// GeoLibre ships Tailwind (with its preflight reset) and ~30 plugin stylesheets
// written for a page of its own. Prefixing every selector with
// :where(html.gis-active) keeps all of that off the GEIDA pages; :where() adds
// no specificity, so GeoLibre's own cascade is exactly what it was.
//
//   .x            -> :where(html.gis-active) .x
//   :root, :host  -> :where(html.gis-active)
//   html.dark .x  -> html:where(.gis-active).dark .x
//   .dark .x      -> html:where(.gis-active).dark .x
//   body          -> :where(html.gis-active) body
//   #root         -> :where(html.gis-active) .gis-root
//
// GEIDA's own stylesheets (src/**) and the two shared libraries GEIDA imports
// (maplibre-gl.css, ol.css) are left alone.
import path from "node:path";

const SCOPE = ":where(html.gis-active)";
const HTML = "html:where(.gis-active)";
const SKIP_AT_RULES = new Set(["keyframes", "-webkit-keyframes", "font-face", "property", "counter-style", "page", "font-feature-values"]);

/** Split a selector list on top-level commas. */
function splitList(sel) {
  const out = [];
  let depth = 0, quote = null, cur = "";
  for (const ch of sel) {
    if (quote) { if (ch === quote) quote = null; cur += ch; continue; }
    if (ch === '"' || ch === "'") { quote = ch; cur += ch; continue; }
    if (ch === "(" || ch === "[") depth++;
    if (ch === ")" || ch === "]") depth--;
    if (ch === "," && depth === 0) { out.push(cur); cur = ""; continue; }
    cur += ch;
  }
  out.push(cur);
  return out;
}

export function scopeSelector(raw) {
  const lead = raw.match(/^\s*/)[0];
  const s = raw.trim();
  if (!s || s.startsWith(SCOPE) || s.startsWith(HTML)) return raw;
  if (/^(:root|:host)(?![\w-])/.test(s)) return lead + s.replace(/^(:root|:host)/, SCOPE);
  if (/^html(?![\w-])/.test(s)) return lead + s.replace(/^html/, HTML);
  if (/^\.dark(?![\w-])/.test(s)) return lead + HTML + s;
  if (/^body(?![\w-])/.test(s)) return lead + `${SCOPE} ${s}`;
  if (/^#root(?![\w-])/.test(s)) return lead + `${SCOPE} .gis-root${s.slice(5)}`;
  if (/^(from|to|\d+(\.\d+)?%)$/.test(s)) return raw; // keyframe step
  return lead + `${SCOPE} ${s}`;
}

// GEIDA's own CSS, the other way round: it is written for GEIDA pages (element
// resets, .lucide sizes, .btn, .menu...) and, being unlayered, would beat
// GeoLibre's layered Tailwind styles. So it applies only while the workspace is
// NOT on screen, except the chrome that stays visible above it (navbar, menus,
// toasts, the workspace frame), which keeps applying - inside .site-header /
// .toasts where its class names are generic.
const NOT_GIS = ":where(html:not(.gis-active))";
const NOT_GIS_HTML = "html:where(:not(.gis-active))";
const CHROME_OWN = /^(site-header|toasts|skip-link|gis-[\w-]+)$/;
const CHROME_SHARED = /^(mark(-[\w-]+)?|primary-nav|nav-[\w-]+|has-menu|menu(-[\w-]+)?|round-btn|account|initial|chev|when-open|when-closed|toast(-[\w-]+)?|lucide)$/;
const CHROME_ROOT = ":where(html.gis-active) :is(.site-header, .toasts)";

export function scopeGeidaSelector(raw) {
  const s = raw.trim();
  if (!s || /^:root(?![\w-])/.test(s)) return [s];
  const classes = [...s.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
  const first = s.split(/[\s>+~]/)[0];
  const firstClasses = [...first.matchAll(/\.([\w-]+)/g)].map((m) => m[1]);
  if (firstClasses.some((c) => CHROME_OWN.test(c))) return [s];
  const geidaOnly = /^html(?![\w-])/.test(s) ? s.replace(/^html/, NOT_GIS_HTML) : `${NOT_GIS} ${s}`;
  if (classes.some((c) => CHROME_SHARED.test(c))) return [geidaOnly, `${CHROME_ROOT} ${s}`];
  return [geidaOnly];
}

export default function scopeGis({ geidaSrc, keep = [] }) {
  const geida = path.resolve(geidaSrc) + path.sep;
  return {
    postcssPlugin: "geida-scope-gis",
    OnceExit(root) {
      const file = root.source?.input?.file ?? "";
      if (!file || keep.some((k) => file.endsWith(k))) return;
      const own = file.startsWith(geida);
      root.walkRules((rule) => {
        for (let p = rule.parent; p && p.type !== "root"; p = p.parent) {
          if (p.type === "atrule" && SKIP_AT_RULES.has(p.name.toLowerCase())) return;
          if (p.type === "rule") return; // nested rule: its parent is already scoped
        }
        const list = splitList(rule.selector);
        rule.selector = own ? list.flatMap(scopeGeidaSelector).join(", ") : list.map(scopeSelector).join(",");
      });
    },
  };
}
scopeGis.postcss = true;
