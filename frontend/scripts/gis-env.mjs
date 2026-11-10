// Build-time settings GeoLibre reads when gis/apps/web/vite.config.ts loads.
// Imported first by vite.config.ts; an explicit environment variable still wins.
process.env.VITE_GEOLIBRE_APP_NAME ??= "GEIDA";
