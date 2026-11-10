// Copies the GeoLibre processing engine (geolibre-wasm + its WASI shim) from
// node_modules into public/vendor so the app serves it itself (no CDN).
//   node scripts/copy-engine.mjs              always copy
//   node scripts/copy-engine.mjs --if-missing  skip when already copied (dev/build hooks)
import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const vendor = join(root, "public", "vendor");
const engineDir = join(vendor, "geolibre-wasm");
const shimDir = join(vendor, "browser_wasi_shim");
const files = ["tools.mjs", "geolibre_wasm.js", "geolibre_wasm_bg.wasm", "geolibre-cli.wasm"];

const pkg = JSON.parse(readFileSync(join(root, "node_modules", "geolibre-wasm", "package.json"), "utf8"));
const stamp = join(engineDir, "VERSION");
if (process.argv.includes("--if-missing") && existsSync(stamp) && readFileSync(stamp, "utf8").trim() === pkg.version) {
  process.exit(0);
}

for (const d of [engineDir, shimDir]) { rmSync(d, { recursive: true, force: true }); mkdirSync(d, { recursive: true }); }
for (const f of files) cpSync(join(root, "node_modules", "geolibre-wasm", f), join(engineDir, f));
const shimSrc = join(root, "node_modules", "@bjorn3", "browser_wasi_shim", "dist");
for (const f of readdirSync(shimSrc)) if (f.endsWith(".js")) cpSync(join(shimSrc, f), join(shimDir, f));

// The runner imports the shim by package name; point it at our copy.
const tools = join(engineDir, "tools.mjs");
writeFileSync(tools, readFileSync(tools, "utf8").replace('from "@bjorn3/browser_wasi_shim"', 'from "../browser_wasi_shim/index.js"'));
writeFileSync(stamp, pkg.version + "\n");
console.log(`geolibre-wasm ${pkg.version} copied to public/vendor`);
