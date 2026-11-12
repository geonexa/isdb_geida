/**
 * Toolbox results shown on the project map. The results themselves are saved on the server (apps/toolbox);
 * this keeps which of them are on the map, with their opacity, for this page visit.
 */
import { useCallback, useState } from "react";

export type ToolLegendItem = { label: string; color: string };
export type ToolLayer = {
  /** `${runId}:${outputName}` */
  id: string; run: number; name: string; source: string; kind: "raster" | "vector";
  /** PNG preview (raster) or GeoJSON (vector) on the server. */
  url: string; bounds?: [number, number, number, number];
  legend: ToolLegendItem[]; color?: string;
  /** Download link (GeoTIFF or GeoPackage). */
  download: string; downloadLabel: string;
  opacity: number; visible: boolean;
};

export const toolFileUrl = (run: number, name: string) => `/api/toolbox/runs/${run}/files/${encodeURIComponent(name)}`;

export function useToolResults() {
  const [layers, setLayers] = useState<ToolLayer[]>([]);
  const patch = useCallback((id: string, p: Partial<ToolLayer>) => setLayers((ls) => ls.map((l) => (l.id === id ? { ...l, ...p } : l))), []);
  const remove = useCallback((id: string) => setLayers((ls) => ls.filter((l) => l.id !== id)), []);
  const removeRun = useCallback((run: number) => setLayers((ls) => ls.filter((l) => l.run !== run)), []);
  const add = useCallback((l: ToolLayer) => setLayers((ls) => [l, ...ls.filter((x) => x.id !== l.id)]), []);
  return { layers, add, patch, remove, removeRun };
}

export function downloadToolLayer(l: ToolLayer) {
  const a = document.createElement("a");
  a.href = `${l.download}?download=1`;
  document.body.appendChild(a); a.click(); a.remove();
}
