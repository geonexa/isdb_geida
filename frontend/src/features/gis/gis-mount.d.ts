// GeoLibre's entry, resolved by vite.config.ts to gis/apps/web/src/mount.tsx.
// Declared here so GEIDA's type-check doesn't descend into GeoLibre's sources
// (they have their own tsconfig).
declare module "virtual:gis-mount" {
  import type { ComponentType, ReactNode } from "react";
  export const GisApp: ComponentType<{ fallback?: ReactNode }>;
}
