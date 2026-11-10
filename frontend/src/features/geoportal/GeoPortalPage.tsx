import "ol/ol.css";
import "@/shared/styles/catalog.css";
import "@/features/geoportal/geoportal.css";
import "@/shared/styles/basemap.css";

import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useLocation } from "react-router-dom";

import { api } from "@/shared/api/client";
import { useAuth } from "@/features/auth/AuthContext";
import { initGeoportal } from "@/features/geoportal/engine/geoportal.js";
import { initToolbox } from "@/features/geoportal/engine/toolbox.js";
import { Markup } from "@/features/geoportal/Markup";
import type { GeoportalConfig } from "@/features/geoportal/types";
import { useBodyClass, useTitle } from "@/shared/lib/dom";

// The processing engine is copied into public/vendor by scripts/copy-engine.mjs.
const VENDOR = "/vendor/geolibre-wasm/";
const ENGINE = {
  mode: "local",
  version: "1.7.1",
  tools: VENDOR + "tools.mjs",
  lib: VENDOR + "geolibre_wasm.js",
  cliWasm: VENDOR + "geolibre-cli.wasm",
  libWasm: VENDOR + "geolibre_wasm_bg.wasm",
};

function Portal({ cfg, signedIn }: { cfg: GeoportalConfig; signedIn: boolean }) {
  const { pathname } = useLocation();
  useEffect(() => {
    const portal = initGeoportal({
      catalog: cfg.catalog,
      basemaps: cfg.basemaps,
      areas: { signedIn, api: "/api/geoportal/areas/", countries: "/data/isdb_member_countries.geojson" },
    });
    const destroyToolbox = initToolbox(portal.G, {
      toolbox: cfg.toolbox,
      clippable: cfg.clippable,
      engine: ENGINE,
      workerUrl: "/processing/geolibre-worker.js",
    });
    return () => { destroyToolbox(); portal.destroy(); };
  }, [cfg, signedIn]);
  return <Markup cfg={cfg} signedIn={signedIn} signInHref={`/accounts/sign-in?next=${encodeURIComponent(pathname)}`} />;
}

export default function GeoPortalPage() {
  useTitle("Data Catalog");
  useBodyClass("page-map");
  const { user, loading } = useAuth();
  const cfg = useQuery({ queryKey: ["gp-config"], queryFn: () => api<GeoportalConfig>("/api/geoportal/config/"), staleTime: Infinity });
  if (cfg.isError) return <p className="wrap section">Couldn't load the Data Catalog: {(cfg.error as Error).message}</p>;
  if (!cfg.data || loading) return null;
  // Remount when the user signs in or out, so the saved-area tools match.
  return <Portal key={user ? `u${user.id}` : "anon"} cfg={cfg.data} signedIn={!!user} />;
}
