import { cpSync, createReadStream, existsSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, type Plugin, type UserConfig } from "vite";

import "./scripts/gis-env.mjs";
import { GIS_WEB_DIR, gisConfig } from "./gis/apps/web/vite.config";

/**
 * One Vite app for all of GEIDA, including the GIS workspace (GeoLibre, under
 * gis/). GeoLibre's build machinery (its plugins, defines, worker and chunking
 * settings) comes from gis/apps/web/vite.config.ts; this file adds GEIDA's
 * entry, aliases and dev proxy, and two bridges:
 *   - GeoLibre's static files (gis/apps/web/public) are served at /gis-assets/
 *     and copied to dist/gis-assets/ on build;
 *   - GeoLibre code that reads import.meta.env.BASE_URL gets "/gis-assets/", so it
 *     finds those files where they are.
 */
const ROOT = path.dirname(fileURLToPath(import.meta.url));
const GIS_DIR = path.join(ROOT, "gis") + path.sep;
const GIS_PUBLIC = path.join(GIS_WEB_DIR, "public");
const GIS_MOUNT = path.join(GIS_WEB_DIR, "src", "mount.tsx");
// Where GeoLibre's static files (gis/apps/web/public) are served. Not /gis/: that
// is where Vite serves the gis/ source folder in development.
const GIS_PUBLIC_URL = "/gis-assets";

// Django runs on :8000. In development Vite forwards the API and the admin to it,
// so the browser sees one origin and the session cookie just works.
const backend = process.env.GEIDA_BACKEND ?? "http://127.0.0.1:8000";
const apiProxy = {
  "/api": { target: backend },
  "/admin": { target: backend },
  "/static/admin": { target: backend },
};

// GeoLibre plugins GEIDA doesn't use: the service worker (GEIDA has none), the
// standalone app's boot-size budget, and the desktop (Tauri) packaging step.
const DROP_PLUGINS = /^(vite-plugin-pwa|geolibre-boot-bundle-budget|geolibre-remove-jupyterlite)/;

const MIME: Record<string, string> = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".mjs": "text/javascript", ".json": "application/json",
  ".css": "text/css", ".wasm": "application/wasm", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml",
  ".ico": "image/x-icon", ".pbf": "application/x-protobuf", ".woff2": "font/woff2", ".woff": "font/woff",
  ".data": "application/octet-stream", ".whl": "application/octet-stream", ".zip": "application/zip",
  ".txt": "text/plain; charset=utf-8", ".py": "text/plain; charset=utf-8", ".ipynb": "application/json",
};

/** Serve gis/apps/web/public at /gis-assets/ in dev; copy it to dist/gis-assets/ on build. */
function gisPublic(): Plugin {
  let outDir = "dist";
  return {
    name: "geida-gis-public",
    configResolved(c) { outDir = path.resolve(c.root, c.build.outDir); },
    configureServer(server) {
      server.middlewares.use(GIS_PUBLIC_URL, (req, res, next) => {
        const rel = decodeURIComponent((req.url ?? "/").split("?")[0]);
        let file = path.join(GIS_PUBLIC, rel);
        if (!file.startsWith(GIS_PUBLIC)) return next();
        if (existsSync(file) && statSync(file).isDirectory()) file = path.join(file, "index.html");
        if (!existsSync(file)) {
          res.statusCode = 404;
          res.end("Not found");
          return;
        }
        res.setHeader("Content-Type", MIME[path.extname(file).toLowerCase()] ?? "application/octet-stream");
        res.setHeader("Cache-Control", "no-cache");
        createReadStream(file).pipe(res);
      });
    },
    closeBundle() {
      if (existsSync(GIS_PUBLIC)) cpSync(GIS_PUBLIC, path.join(outDir, GIS_PUBLIC_URL.slice(1)), { recursive: true });
    },
  };
}

/** GeoLibre code: BASE_URL -> the /gis-assets/ folder its static files are served from. */
function gisBaseUrl(): Plugin {
  return {
    name: "geida-gis-base-url",
    enforce: "pre",
    transform(code, id) {
      if (!id.startsWith(GIS_DIR) || id.includes("node_modules") || !code.includes("import.meta.env.BASE_URL")) return null;
      return { code: code.replaceAll("import.meta.env.BASE_URL", `(import.meta.env.BASE_URL + "${GIS_PUBLIC_URL.slice(1)}/")`), map: null };
    },
  };
}

/**
 * GeoLibre entry points GEIDA imports without type-checking GeoLibre's sources
 * (each has a hand-written declaration in src/):
 *   virtual:gis-mount     - the Analytics workspace (features/gis)
 *   virtual:gis-print     - the print-layout drawing engine (features/print)
 *   virtual:gis-print-svg - its editable-SVG replay
 */
const GIS_VIRTUAL: Record<string, string> = {
  "virtual:gis-mount": GIS_MOUNT,
  "virtual:gis-print": path.join(GIS_WEB_DIR, "src", "lib", "print-layout.ts"),
  "virtual:gis-print-svg": path.join(GIS_WEB_DIR, "src", "lib", "print-layout-svg.ts"),
};
function gisMount(): Plugin {
  return {
    name: "geida-gis-mount",
    resolveId(id) { return GIS_VIRTUAL[id] ?? null; },
  };
}

// Packages GeoLibre has its own (different) version of in gis/apps/web/node_modules.
// Its config dedupes them "from the app root", which used to be gis/apps/web; point
// them there explicitly now that the root is frontend/.
const GIS_OWN_DEPS = ["@anthropic-ai/sdk", "openai"].filter((d) => existsSync(path.join(GIS_WEB_DIR, "node_modules", d)));

const gis = gisConfig as UserConfig;
const gisPlugins = (gis.plugins ?? []).flat().filter((p): p is Plugin => !!p && typeof p === "object" && "name" in p && !DROP_PLUGINS.test(p.name));
const gisAlias = (gis.resolve?.alias as { find: string | RegExp; replacement: string }[]).filter((a) => a.find !== "@");

export default defineConfig({
  ...gis,
  root: ROOT,
  base: "/",
  publicDir: path.join(ROOT, "public"),
  plugins: [gisMount(), gisBaseUrl(), gisPublic(), ...gisPlugins],
  resolve: {
    ...gis.resolve,
    alias: [
      { find: "@", replacement: path.join(ROOT, "src") },
      ...GIS_OWN_DEPS.map((d) => ({ find: d, replacement: path.join(GIS_WEB_DIR, "node_modules", d) })),
      ...gisAlias,
    ],
    dedupe: gis.resolve?.dedupe?.filter((d) => !GIS_OWN_DEPS.includes(d)),
  },
  server: {
    port: 5173,
    strictPort: true,
    host: "localhost",
    proxy: apiProxy,
    watch: { ignored: ["**/src-tauri/**", "**/gis/apps/web/public/**"] },
  },
  preview: { port: 4173, proxy: apiProxy },
  optimizeDeps: {
    ...gis.optimizeDeps,
    // Scan GeoLibre too, so its dependencies are pre-bundled at startup instead
    // of being discovered (and reloading the page) when Analytics first opens.
    entries: ["index.html", path.relative(ROOT, GIS_MOUNT)],
  },
  build: {
    ...gis.build,
    outDir: "dist",
    emptyOutDir: true,
    rollupOptions: { ...gis.build?.rollupOptions, input: { main: path.join(ROOT, "index.html") } },
  },
});
