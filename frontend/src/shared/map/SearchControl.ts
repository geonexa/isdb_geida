/**
 * Map button (same look as zoom and fullscreen) that opens a place search box beside it.
 * Admin units are suggested while typing; Enter also searches towns and other places
 * (GET /api/geoportal/search/, see backend apps/geoportal/search.py). Choosing a result
 * zooms the map to it and marks it with a label.
 */
import * as maplibregl from "maplibre-gl";

import { api } from "@/shared/api/client";

type Result = { name: string; detail: string; kind: string; source: "admin" | "osm"; bbox: [number, number, number, number]; center: [number, number] };

const SEARCH_ICON = '<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>';
const CLOSE_ICON = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>';

export class SearchControl implements maplibregl.IControl {
  private map?: maplibregl.Map;
  private el?: HTMLDivElement;
  private panel?: HTMLDivElement;
  private input?: HTMLInputElement;
  private list?: HTMLUListElement;
  private status?: HTMLParagraphElement;
  private button?: HTMLButtonElement;
  private popup?: maplibregl.Popup;
  private timer?: number;
  private seq = 0;
  private results: Result[] = [];
  private active = -1;

  onAdd(map: maplibregl.Map) {
    this.map = map;
    const el = (this.el = document.createElement("div"));
    el.className = "maplibregl-ctrl maplibregl-ctrl-group pmap-search";
    const b = (this.button = document.createElement("button"));
    b.type = "button";
    b.className = "pmap-search-btn";
    b.title = "Search a place";
    b.setAttribute("aria-label", "Search a place");
    b.setAttribute("aria-expanded", "false");
    b.innerHTML = SEARCH_ICON;
    b.addEventListener("click", () => this.toggle());

    const panel = (this.panel = document.createElement("div"));
    panel.className = "pmap-search-panel";
    panel.hidden = true;
    panel.innerHTML = `<form class="pmap-search-form" role="search">
        <input type="search" placeholder="Search a place or admin unit" aria-label="Search a place or admin unit" autocomplete="off" />
        <button type="button" class="pmap-search-close" title="Close" aria-label="Close search">${CLOSE_ICON}</button>
      </form>
      <ul class="pmap-search-results" role="listbox"></ul>
      <p class="pmap-search-status" aria-live="polite"></p>`;
    this.input = panel.querySelector("input")!;
    this.list = panel.querySelector("ul")!;
    this.status = panel.querySelector("p")!;
    panel.querySelector("form")!.addEventListener("submit", (e) => {
      e.preventDefault();
      window.clearTimeout(this.timer); // the typing search must not replace this one
      if (this.active >= 0 && this.results[this.active]) this.choose(this.results[this.active]);
      else this.search(true);
    });
    panel.querySelector(".pmap-search-close")!.addEventListener("click", () => this.toggle(false));
    this.input.addEventListener("input", () => {
      window.clearTimeout(this.timer);
      this.timer = window.setTimeout(() => this.search(false), 300);
    });
    this.input.addEventListener("keydown", (e) => this.onKey(e));
    // Keep map gestures (drag, wheel, double-click) from starting inside the panel.
    for (const ev of ["mousedown", "wheel", "dblclick", "touchstart"]) panel.addEventListener(ev, (e) => e.stopPropagation());

    el.append(b, panel);
    return el;
  }

  onRemove() {
    window.clearTimeout(this.timer);
    this.popup?.remove();
    this.el?.remove();
    this.map = undefined;
  }

  private toggle(open = this.panel?.hidden ?? true) {
    if (!this.panel || !this.button) return;
    this.panel.hidden = !open;
    this.button.setAttribute("aria-expanded", String(open));
    this.el?.classList.toggle("is-open", open);
    if (open) this.input?.focus();
  }

  private onKey(e: KeyboardEvent) {
    if (e.key === "Escape") { this.toggle(false); this.button?.focus(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    if (!this.results.length) return;
    const n = this.results.length;
    this.active = e.key === "ArrowDown" ? (this.active + 1) % n : (this.active - 1 + n) % n;
    this.render();
  }

  private async search(places: boolean) {
    const q = this.input?.value.trim() ?? "";
    const seq = ++this.seq;
    if (q.length < 2) { this.results = []; this.active = -1; this.setStatus(""); this.render(); return; }
    this.setStatus(places ? "Searching places…" : "");
    try {
      const d = await api<{ results: Result[]; note?: string }>(`/api/geoportal/search/?q=${encodeURIComponent(q)}${places ? "&places=1" : ""}`);
      if (seq !== this.seq) return; // a newer search started
      this.results = d.results;
      this.active = -1;
      this.render();
      this.setStatus(d.note || (d.results.length ? (places ? "" : "Press Enter to search towns and other places too.") : `No match for “${q}”.`));
    } catch {
      if (seq === this.seq) this.setStatus("Search failed. Try again.");
    }
  }

  private setStatus(text: string) {
    if (this.status) { this.status.textContent = text; this.status.hidden = !text; }
  }

  private render() {
    const list = this.list;
    if (!list) return;
    // Keep the list inside the map: room below the search box, at most 280 px.
    const room = (this.map?.getContainer().clientHeight ?? 400) - (this.el?.offsetTop ?? 0) - 90;
    list.style.maxHeight = `${Math.max(110, Math.min(280, room))}px`;
    list.replaceChildren(...this.results.map((r, i) => {
      const li = document.createElement("li");
      li.setAttribute("role", "option");
      li.setAttribute("aria-selected", String(i === this.active));
      li.className = i === this.active ? "is-active" : "";
      const name = document.createElement("strong");
      name.textContent = r.name;
      const meta = document.createElement("span");
      meta.textContent = [r.kind, r.detail].filter(Boolean).join(" · ");
      li.append(name, meta);
      li.addEventListener("click", () => this.choose(r));
      return li;
    }));
  }

  private choose(r: Result) {
    const m = this.map;
    if (!m) return;
    const [w, s, e, n] = r.bbox;
    if (e - w < 1e-6 && n - s < 1e-6) m.flyTo({ center: r.center, zoom: 13 });
    else m.fitBounds([[w, s], [e, n]], { padding: 48, maxZoom: 14, duration: 900 });
    this.popup?.remove();
    this.popup = new maplibregl.Popup({ className: "pmap-popup", closeButton: true, focusAfterOpen: false, offset: 6 })
      .setLngLat(r.center).setText(r.name).addTo(m);
    this.toggle(false);
  }
}
