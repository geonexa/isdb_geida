// Prepares the files `vite` serves that aren't produced by Vite itself:
//   - the GeoLibre processing engine (geolibre-wasm) in public/vendor (Geo-Portal tools);
//   - the JupyterLite site behind the Analytics Notebook panel (optional: needs
//     `pip install -r gis/apps/web/jupyterlite/requirements.txt`, skipped otherwise).
//   node scripts/predev.mjs           dev: only what is missing
//   node scripts/predev.mjs --build   build: refresh both
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const build = process.argv.includes("--build");

function run(script, args) {
  const r = spawnSync(process.execPath, [join(root, script), ...args], { cwd: root, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

run("scripts/copy-engine.mjs", build ? [] : ["--if-missing"]);
run("gis/scripts/build-jupyterlite.mjs", build ? [] : ["--if-missing"]);
