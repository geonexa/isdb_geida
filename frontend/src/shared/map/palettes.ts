/**
 * Colour palettes users can pick for map layers. Names match TiTiler / rio-tiler
 * colormaps, so the same name recolours a raster on the tile server
 * (backend/apps/geoportal/raster.py PALETTES) and a vector layer in the browser.
 * A name ending in "_r" is the palette reversed.
 */
export const PALETTES: Record<string, { label: string; stops: string[] }> = {
  viridis: { label: "Viridis", stops: ["#440154", "#414487", "#2a788e", "#22a884", "#7ad151", "#fde725"] },
  plasma: { label: "Plasma", stops: ["#0d0887", "#6a00a8", "#b12a90", "#e16462", "#fca636", "#f0f921"] },
  magma: { label: "Magma", stops: ["#000004", "#3b0f70", "#8c2981", "#de4968", "#fe9f6d", "#fcfdbf"] },
  cividis: { label: "Cividis", stops: ["#00224e", "#35456c", "#666970", "#948e77", "#c8b866", "#fee838"] },
  ylgnbu: { label: "Yellow–green–blue", stops: ["#ffffd9", "#c7e9b4", "#7fcdbb", "#41b6c4", "#1d91c0", "#225ea8", "#0c2c84"] },
  gnbu: { label: "Green–blue", stops: ["#f7fcf0", "#ccebc5", "#a8ddb5", "#7bccc4", "#43a2ca", "#0868ac"] },
  ylgn: { label: "Yellow–green", stops: ["#ffffe5", "#d9f0a3", "#addd8e", "#78c679", "#31a354", "#006837"] },
  ylorrd: { label: "Yellow–orange–red", stops: ["#ffffcc", "#fed976", "#feb24c", "#fd8d3c", "#f03b20", "#bd0026"] },
  orrd: { label: "Orange–red", stops: ["#fff7ec", "#fdd49e", "#fdbb84", "#fc8d59", "#e34a33", "#b30000"] },
  rdylgn: { label: "Red–yellow–green", stops: ["#a50026", "#f46d43", "#fee08b", "#d9ef8b", "#66bd63", "#006837"] },
  spectral: { label: "Spectral", stops: ["#9e0142", "#f46d43", "#fee08b", "#e6f598", "#66c2a5", "#5e4fa2"] },
  blues: { label: "Blues", stops: ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"] },
  greens: { label: "Greens", stops: ["#f7fcf5", "#c7e9c0", "#74c476", "#238b45", "#00441b"] },
  reds: { label: "Reds", stops: ["#fff5f0", "#fcbba1", "#fb6a4a", "#cb181d", "#67000d"] },
  greys: { label: "Greys", stops: ["#ffffff", "#d9d9d9", "#969696", "#525252", "#000000"] },
  terrain: { label: "Terrain", stops: ["#333399", "#0294fa", "#24d36d", "#fefe98", "#805c54", "#fcfbfb"] },
};

/** Colour stops of a palette name ("viridis", "viridis_r"); null if unknown. */
export function paletteStops(name: string): string[] | null {
  const rev = name.endsWith("_r");
  const p = PALETTES[rev ? name.slice(0, -2) : name];
  return p ? (rev ? [...p.stops].reverse() : p.stops) : null;
}

const hex = (c: string) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16));
const toHex = (v: number[]) => "#" + v.map((x) => Math.round(x).toString(16).padStart(2, "0")).join("");

/** n colours evenly spaced along a palette (for classes and steps). */
export function samplePalette(name: string, n: number): string[] {
  const stops = paletteStops(name) ?? PALETTES.viridis.stops;
  if (n <= 1) return [stops[Math.floor(stops.length / 2)]];
  return Array.from({ length: n }, (_, i) => {
    const t = (i / (n - 1)) * (stops.length - 1);
    const a = Math.floor(t), b = Math.min(stops.length - 1, a + 1), f = t - a;
    const [ca, cb] = [hex(stops[a]), hex(stops[b])];
    return toHex(ca.map((v, k) => v + (cb[k] - v) * f));
  });
}

export const cssGradient = (name: string) => `linear-gradient(90deg, ${(paletteStops(name) ?? []).join(",")})`;
