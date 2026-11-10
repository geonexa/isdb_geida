/**
 * User display settings for map layers in the project workspace. The module's own style
 * is the starting point; these overrides change only what the user touched, and are kept
 * per project in the browser.
 */
import type { VectorStyle } from "@/features/projects/types";
import { samplePalette } from "@/shared/map/palettes";

export type VectorOverride = {
  /** Single colour (layers without classes or steps). */
  color?: string;
  /** Recolour classes or steps along a palette. */
  palette?: string;
  /** 0–1: fill opacity for polygons, opacity of points and lines. */
  opacity?: number;
  /** Multiplier for point radius and line width. */
  size?: number;
  /** Outline of points and polygons. */
  outline?: string;
};
export type ImageOverride = { opacity?: number };

export type LayerStyles = {
  vectors: Record<string, VectorOverride>;
  images: Record<string, ImageOverride>;
  area: { color: string; fillOpacity: number; visible?: boolean };
  basemap: { visible: boolean; background: string };
};

export const DEFAULT_STYLES: LayerStyles = {
  vectors: {}, images: {},
  area: { color: "#0B3B47", fillOpacity: 0.18 },
  basemap: { visible: true, background: "#E9ECEE" },
};

/** The module's style with the user's override applied. */
export function applyVectorOverride(s: VectorStyle, ov?: VectorOverride): VectorStyle & { outline?: string; lineOpacity?: number } {
  if (!ov) return s;
  const out: VectorStyle & { outline?: string; lineOpacity?: number } = { ...s };
  if (ov.color && !(s.property && (s.classes?.length || s.steps?.length))) out.color = ov.color;
  if (ov.palette && s.property && s.classes?.length) {
    const cols = samplePalette(ov.palette, s.classes.length);
    out.classes = s.classes.map((c, i) => ({ ...c, color: cols[i] }));
  }
  if (ov.palette && s.property && s.steps?.length) {
    const cols = samplePalette(ov.palette, s.steps.length);
    out.steps = s.steps.map((x, i) => ({ ...x, color: cols[i] }));
  }
  if (ov.opacity != null) { out.opacity = ov.opacity; out.lineOpacity = ov.opacity; }
  if (ov.size != null) {
    out.radius = (s.radius ?? 4.5) * ov.size;
    out.width = (s.width ?? 1.6) * ov.size;
    if (s.classes) out.classes = (out.classes ?? s.classes).map((c) => ({ ...c, radius: c.radius != null ? c.radius * ov.size! : c.radius, width: c.width != null ? c.width * ov.size! : c.width }));
  }
  if (ov.outline) out.outline = ov.outline;
  return out;
}

const key = (code: string) => `geida.layerStyles.${code}`;
export function loadStyles(code: string): LayerStyles {
  try {
    const raw = localStorage.getItem(key(code));
    return raw ? { ...DEFAULT_STYLES, ...JSON.parse(raw) } : DEFAULT_STYLES;
  } catch { return DEFAULT_STYLES; }
}
export function saveStyles(code: string, s: LayerStyles) {
  try { localStorage.setItem(key(code), JSON.stringify(s)); } catch { /* convenience only */ }
}
