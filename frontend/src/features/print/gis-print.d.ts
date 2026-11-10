// GeoLibre's print-layout engine (gis/apps/web/src/lib/print-layout.ts and
// print-layout-svg.ts), resolved by vite.config.ts. Declared here, for the part
// GEIDA uses, so GEIDA's type-check doesn't descend into GeoLibre's sources.
// Keep in step with LayoutOptions in print-layout.ts when GeoLibre is updated.
declare module "virtual:gis-print" {
  export type PaperSizeId = "a4" | "a3" | "letter" | "legal" | "tabloid" | "fullhd" | "hd" | "uhd4k" | "square" | "custom";
  export type Orientation = "portrait" | "landscape";
  export type SizeUnit = "mm" | "px";
  export type BodyCorner = "top-left" | "top-right" | "bottom-left" | "bottom-right";

  export interface PaperSize { id: PaperSizeId; label: string; width: number; height: number; unit: SizeUnit; group: "paper" | "screen" }
  export interface ResolvedPageSize { width: number; height: number; unit: SizeUnit }
  export interface CustomSize { width: number; height: number; unit: SizeUnit }

  export interface LegendSwatch { color: string; label?: string; size?: number }
  export interface LegendEntry { id: string; name: string; swatches: LegendSwatch[] }

  export interface LayoutOptions {
    title: string;
    subtitle: string;
    paperSize: PaperSizeId;
    orientation: Orientation;
    customSize?: CustomSize | null;
    showTitle: boolean;
    showSubtitle?: boolean;
    titlePlacement?: "outside" | "inside";
    titleAlign?: "left" | "center" | "right";
    showLegend: boolean;
    showScaleBar: boolean;
    scaleUnit?: "metric" | "imperial" | "nautical";
    showNorthArrow: boolean;
    navigationGrouped?: boolean;
    showInfoBlock?: boolean;
    author?: string;
    projectNumber?: string;
    crs?: string;
    revision?: string;
    showFooter: boolean;
    footerText: string;
    showDate?: boolean;
    dateText?: string;
    showAttribution?: boolean;
    attributionText?: string;
    pageMargin?: "normal" | "narrow" | "none";
    showPageBorder?: boolean;
    pageBorderColor?: string;
    pageBorderWidth?: number;
    mapBorderColor?: string;
    mapBorderWidth?: number;
    mapBackground?: string;
    colorbar?: {
      colors: readonly string[]; min: number; max: number; label?: string;
      orientation: "horizontal" | "vertical"; position: BodyCorner; lengthPct?: number;
    } | null;
    legend: LegendEntry[];
    legendTitle: string;
    legendGroupByLayer: boolean;
    metersPerPixel: number;
    mapPixelRatio?: number;
    bearingDeg: number;
    mapImage: CanvasImageSource | null;
    mapImageWidth: number;
    mapImageHeight: number;
    mapFit?: "cover" | "contain";
  }

  export const PAPER_SIZES: PaperSize[];
  export function resolvePageSize(opts: { paperSize: PaperSizeId; orientation: Orientation; customSize?: CustomSize | null }): ResolvedPageSize;
  export function pageMm(size: ResolvedPageSize): { widthMm: number; heightMm: number };
  export function pagePx(size: ResolvedPageSize, dpi: number): { width: number; height: number };
  export function mapBodyAspectRatio(opts: LayoutOptions): number;
  export function computeScaleRatio(opts: LayoutOptions): number;
  export function drawLayoutContext(ctx: CanvasRenderingContext2D, W: number, H: number, opts: LayoutOptions): void;
}

declare module "virtual:gis-print-svg" {
  import type { LayoutOptions } from "virtual:gis-print";
  /** The page as editable SVG at 150 dpi (viewBox in those pixels). */
  export function renderLayoutSvg(opts: LayoutOptions): string;
}
