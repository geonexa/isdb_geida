/** Export formats: SVG (vector, editable), PNG, PDF, clipboard and the browser's print dialog. */
import outfitUrl from "@fontsource-variable/outfit/files/outfit-latin-wght-normal.woff2?url";

import { pageSize, type Layout } from "@/features/print/layout";
import { svgDocument, type Rendered } from "@/features/print/render";

/** Browsers refuse canvases much larger than this (Safari: ~16 MP; Chrome: ~250 MP). */
const MAX_PIXELS = 100_000_000;

let fontCss: Promise<string> | null = null;
/** @font-face for Outfit, embedded so exports look the same everywhere. */
export function embeddedFontCss() {
  fontCss ??= fetch(outfitUrl).then((r) => r.blob()).then(toDataUrl)
    .then((url) => `@font-face{font-family:"Outfit";font-weight:100 900;font-style:normal;src:url(${url}) format("woff2");}`)
    .catch(() => "");
  return fontCss;
}

export const toDataUrl = (b: Blob) => new Promise<string>((ok, fail) => { const fr = new FileReader(); fr.onload = () => ok(String(fr.result)); fr.onerror = () => fail(fr.error); fr.readAsDataURL(b); });

/** Image (same origin or data URL) as a data URL and its natural size. */
export async function loadPicture(src: string) {
  const href = src.startsWith("data:") ? src : await fetch(src).then((r) => { if (!r.ok) throw new Error(`Couldn't load ${src}`); return r.blob(); }).then(toDataUrl);
  const el = new Image();
  el.src = href;
  await el.decode();
  return { href, w: el.naturalWidth, h: el.naturalHeight };
}

function download(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/** The dpi actually usable for this page (large pages at high dpi exceed canvas limits). */
export function usableDpi(layout: Layout, dpi: number) {
  const { w, h } = pageSize(layout.page);
  const px = (w / 25.4) * (h / 25.4);
  return Math.min(dpi, Math.floor(Math.sqrt(MAX_PIXELS / px)));
}

/** Rasterise the SVG page at `dpi`. */
export async function rasterize(r: Rendered, css: string, dpi: number) {
  const W = Math.round((r.width / 25.4) * dpi), H = Math.round((r.height / 25.4) * dpi);
  const url = URL.createObjectURL(new Blob([svgDocument(r, css)], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("The page is too large to render at this resolution. Lower the resolution.");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, W, H);
    ctx.drawImage(img, 0, 0, W, H);
    return canvas;
  } finally {
    URL.revokeObjectURL(url);
  }
}

const toBlob = (c: HTMLCanvasElement, type = "image/png", q?: number) =>
  new Promise<Blob>((ok, fail) => c.toBlob((b) => (b ? ok(b) : fail(new Error("The page is too large to render. Lower the resolution."))), type, q));

export async function exportSvg(r: Rendered, name: string) {
  download(new Blob([svgDocument(r, await embeddedFontCss())], { type: "image/svg+xml" }), `${name}.svg`);
}

export async function exportPng(r: Rendered, dpi: number, name: string) {
  download(await toBlob(await rasterize(r, await embeddedFontCss(), dpi)), `${name}.png`);
}

export async function exportPdf(r: Rendered, dpi: number, name: string, meta: { title: string; subject: string }) {
  const [{ jsPDF }, canvas] = await Promise.all([import("jspdf"), rasterize(r, await embeddedFontCss(), dpi)]);
  const pdf = new jsPDF({ orientation: r.width >= r.height ? "landscape" : "portrait", unit: "mm", format: [r.width, r.height], compress: true });
  pdf.setProperties({ title: meta.title, subject: meta.subject, creator: "GEIDA - IsDB Geoinformatics Data Platform" });
  pdf.addImage(canvas, "PNG", 0, 0, r.width, r.height, undefined, "FAST");
  download(pdf.output("blob"), `${name}.pdf`);
}

export async function copyPng(r: Rendered) {
  if (typeof ClipboardItem === "undefined" || !navigator.clipboard?.write) throw new Error("This browser can't copy images. Download a PNG instead.");
  const css = await embeddedFontCss();
  // The blob goes in as a promise so the write starts inside the click (Safari needs that).
  await navigator.clipboard.write([new ClipboardItem({ "image/png": rasterize(r, css, 150).then((c) => toBlob(c)) })]);
}

/** Print through the browser's dialog, one page at the layout's paper size. */
export async function printPage(r: Rendered, dpi: number, title: string) {
  const url = URL.createObjectURL(await toBlob(await rasterize(r, await embeddedFontCss(), dpi)));
  const frame = document.createElement("iframe");
  frame.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
  document.body.appendChild(frame);
  const doc = frame.contentDocument!;
  doc.open();
  doc.write(`<!doctype html><title>${title.replace(/</g, "&lt;")}</title><style>@page{size:${r.width}mm ${r.height}mm;margin:0}html,body{margin:0}img{display:block;width:${r.width}mm;height:${r.height}mm}</style><img src="${url}">`);
  doc.close();
  const img = doc.querySelector("img")!;
  await (img.complete ? Promise.resolve() : new Promise((ok) => { img.onload = ok; }));
  frame.contentWindow!.focus();
  frame.contentWindow!.print();
  setTimeout(() => { frame.remove(); URL.revokeObjectURL(url); }, 60_000);
}
