// MapLibre 6 starts its worker from a URL next to the main bundle, which Vite's
// dependency pre-bundling breaks. Point it at the worker asset Vite emits.
import { setWorkerUrl } from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

setWorkerUrl(workerUrl);
