// Prepares the files `vite` serves that aren't produced by Vite itself:
//   - the JupyterLite site behind the Analytics Notebook panel (optional: needs
//     `pip install -r gis/apps/web/jupyterlite/requirements.txt`, skipped otherwise);
//   - @geolibre/embed (gis/packages/embed/dist, git-ignored), whose types GeoLibre
//     imports: a fresh clone has no dist/ and the type-check fails without it.
//   node scripts/predev.mjs           dev: only what is missing
//   node scripts/predev.mjs --build   build: refresh all
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const build = process.argv.includes("--build");

function run(script, args) {
  const r = spawnSync(process.execPath, [join(root, script), ...args], { cwd: root, stdio: "inherit" });
  if (r.status !== 0) process.exit(r.status ?? 1);
}

run("gis/scripts/build-jupyterlite.mjs", build ? [] : ["--if-missing"]);

const embed = join(root, "gis", "packages", "embed");
if (build || !existsSync(join(embed, "dist", "index.d.ts"))) {
  run("node_modules/typescript/bin/tsc", ["-p", join(embed, "tsconfig.build.json")]);
  console.log("@geolibre/embed built to gis/packages/embed/dist");
}
