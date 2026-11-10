/** HTML for the popup shown when a feature of an analysis layer is clicked: its OSM tags and computed values. */

const OSM_REF = /^(node|way|relation)\/\d+$/;
const esc = (v: unknown) => String(v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);

function value(v: unknown) {
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
  return String(v);
}

/** `layer`: the analysis layer's title, shown above the feature name. */
export function featurePopupHtml(props: Record<string, unknown>, layer: string) {
  const name = props.name ? String(props.name) : "";
  const ref = typeof props.osm_id === "string" && OSM_REF.test(props.osm_id) ? props.osm_id : "";
  const rows = Object.entries(props)
    .filter(([k, v]) => k !== "name" && k !== "osm_id" && v !== null && v !== undefined && v !== "")
    .map(([k, v]) => `<tr><th>${esc(k)}</th><td>${esc(value(v))}</td></tr>`)
    .join("");
  return `<div class="fpop">
    <div class="fpop-layer">${esc(layer)}</div>
    <div class="fpop-name${name ? "" : " is-empty"}">${esc(name || "(no name)")}</div>
    ${rows ? `<div class="fpop-scroll"><table>${rows}</table></div>` : `<p class="fpop-none">No attributes.</p>`}
    ${ref ? `<a class="fpop-osm" href="https://www.openstreetmap.org/${ref}" target="_blank" rel="noopener noreferrer">${esc(ref)} · View on OpenStreetMap ↗</a>` : ""}
  </div>`;
}
