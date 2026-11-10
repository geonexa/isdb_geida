import path from "node:path";
import { fileURLToPath } from "node:url";

import tailwind from "@tailwindcss/postcss";

import scopeGis from "./scripts/postcss-scope-gis.mjs";

const root = path.dirname(fileURLToPath(import.meta.url));

export default {
  plugins: [
    // GeoLibre's Tailwind setup (gis/apps/web/src/index.css), scanning its sources as before.
    tailwind({ base: path.join(root, "gis/apps/web") }),
    // ...and its styles scoped to the Analytics page.
    scopeGis({ geidaSrc: path.join(root, "src"), keep: ["maplibre-gl/dist/maplibre-gl.css", "ol/ol.css"] }),
  ],
};
