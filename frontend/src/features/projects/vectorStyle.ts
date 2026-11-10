/** MapLibre paint and legend entries for a run's vector output (style from the module; see modules/README.md). */
import type { ExpressionSpecification } from "maplibre-gl";

import type { VectorStyle } from "@/features/projects/types";

const TEAL = "#0B3B47";
type Expr = ExpressionSpecification | string | number;

/** Colour, or a match/step expression on `style.property`. */
export function colorExpr(s: VectorStyle): Expr {
  const base = s.color ?? TEAL;
  if (s.property && s.classes?.length) {
    return ["match", ["to-string", ["get", s.property]], ...s.classes.flatMap((c) => [String(c.value), c.color]), base] as ExpressionSpecification;
  }
  if (s.property && s.steps?.length) {
    const [first, ...rest] = s.steps;
    return ["step", ["to-number", ["get", s.property], 0], first.color, ...rest.flatMap((x) => [x.from, x.color])] as ExpressionSpecification;
  }
  return base;
}

function perClass(s: VectorStyle, key: "radius" | "width", fallback: number): Expr {
  const own = s[key] ?? fallback;
  const sized = s.classes?.filter((c) => c[key] != null) ?? [];
  if (!s.property || !sized.length) return own;
  return ["match", ["to-string", ["get", s.property]], ...sized.flatMap((c) => [String(c.value), c[key]!]), own] as ExpressionSpecification;
}

export const radiusExpr = (s: VectorStyle) => perClass(s, "radius", 4.5);
export const widthExpr = (s: VectorStyle) => perClass(s, "width", 1.6);

/** Legend swatches: one per class or step, else a single swatch. */
export function legendSwatches(s: VectorStyle): { color: string; label?: string; size?: number }[] {
  if (s.property && s.classes?.length) return s.classes.map((c) => ({ color: c.color, label: c.label, size: c.radius }));
  if (s.property && s.steps?.length) return s.steps.map((x) => ({ color: x.color, label: x.label }));
  return [{ color: s.color ?? TEAL, size: s.radius ?? 4.5 }];
}
