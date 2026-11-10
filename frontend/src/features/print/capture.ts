/**
 * Map capture for print: a hidden MapLibre map with the live map's style, sized to
 * the map item's frame and rendered at the export resolution. Prints are therefore
 * sharp at any paper size and show exactly the item's extent, not a stretched
 * screenshot of the screen map.
 */
import * as maplibregl from "maplibre-gl";

export type BBox = [number, number, number, number];

export type CapturedMap = {
  image: HTMLCanvasElement;
  /** What the image shows: [west, south, east, north] (Web Mercator, north up). */
  bounds: BBox;
  center: [number, number];
  zoom: number;
  /** Ground metres per image pixel at the centre. */
  metersPerPixel: number;
  /** Image pixels per CSS pixel. */
  pixelRatio: number;
};

const EARTH = 40075016.686;
/** WebGL canvases above this size fail on many GPUs. */
const MAX_SIDE = 8192;
const TIMEOUT_MS = 45_000;
/** Frame sizes are CSS pixels at 96 per inch. */
export const MM_TO_CSS = 96 / 25.4;

export const metersPerCssPixel = (zoom: number, lat: number) => (EARTH * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** zoom);
/** Zoom at which 1 mm on paper is `scale` mm on the ground (frame at 96 CSS px per inch). */
export const zoomForScale = (scale: number, lat: number) => Math.log2((EARTH * Math.cos((lat * Math.PI) / 180)) / (512 * (scale / 1000) / MM_TO_CSS));
/** The 1:N scale of a capture, for a frame `widthMm` wide. */
export const scaleOf = (c: CapturedMap, widthMm: number) => (c.metersPerPixel * c.image.width) / (widthMm / 1000);

export type Camera =
  | { kind: "bounds"; bbox: BBox; padding?: number }
  | { kind: "center"; center: [number, number]; scale: number };

export type CaptureRequest = {
  /** Frame size, mm. */
  widthMm: number;
  heightMm: number;
  /** Output dots per inch (96 = screen). */
  dpi: number;
  camera: Camera;
};

export async function captureMap(live: maplibregl.Map, req: CaptureRequest): Promise<CapturedMap> {
  const width = Math.max(20, Math.round(req.widthMm * MM_TO_CSS));
  const height = Math.max(20, Math.round(req.heightMm * MM_TO_CSS));
  const ratio = Math.max(0.5, Math.min(req.dpi / 96, MAX_SIDE / width, MAX_SIDE / height));
  const host = document.createElement("div");
  host.style.cssText = `position:fixed;left:-${width + 100}px;top:0;width:${width}px;height:${height}px;pointer-events:none;visibility:hidden`;
  document.body.appendChild(host);

  const cam = req.camera;
  const camera: Partial<maplibregl.MapOptions> = cam.kind === "bounds"
    ? { bounds: [[cam.bbox[0], cam.bbox[1]], [cam.bbox[2], cam.bbox[3]]], fitBoundsOptions: { padding: cam.padding ?? 0 } }
    : { center: cam.center, zoom: zoomForScale(cam.scale, cam.center[1]) };

  const map = new maplibregl.Map({
    container: host,
    style: live.getStyle(),
    ...camera,
    bearing: 0,
    interactive: false,
    attributionControl: false,
    fadeDuration: 0,
    pixelRatio: ratio,
    maxZoom: 22,
    renderWorldCopies: false,
    canvasContextAttributes: { preserveDrawingBuffer: true, antialias: true },
  });
  try {
    await new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error("The map took too long to draw. Try a smaller page or a lower resolution.")), TIMEOUT_MS);
      map.once("idle", () => { window.clearTimeout(timer); resolve(); });
      map.on("error", (e) => { if (!(e as { sourceId?: string }).sourceId) { window.clearTimeout(timer); reject(e.error ?? new Error("The map couldn't be drawn.")); } });
    });
    const src = map.getCanvas();
    const image = document.createElement("canvas");
    image.width = src.width;
    image.height = src.height;
    image.getContext("2d")!.drawImage(src, 0, 0);
    const b = map.getBounds();
    const c = map.getCenter();
    return {
      image, pixelRatio: ratio, zoom: map.getZoom(), center: [c.lng, c.lat],
      bounds: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
      metersPerPixel: metersPerCssPixel(map.getZoom(), c.lat) / ratio,
    };
  } finally {
    map.remove();
    host.remove();
  }
}

/* Web Mercator helpers for drawing on top of a capture. */
export const mercY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + (Math.max(-85, Math.min(85, lat)) * Math.PI) / 360));
export const unmercY = (y: number) => (Math.atan(Math.exp(y)) * 360) / Math.PI - 90;

/** lon/lat -> position in a w x h frame showing `bounds`. */
export function projector(bounds: BBox, w: number, h: number) {
  const [W, S, E, N] = bounds;
  const yn = mercY(N), ys = mercY(S);
  return {
    x: (lon: number) => ((lon - W) / (E - W)) * w,
    y: (lat: number) => ((yn - mercY(lat)) / (yn - ys)) * h,
    lon: (x: number) => W + (x / w) * (E - W),
    lat: (y: number) => unmercY(yn - (y / h) * (yn - ys)),
  };
}
