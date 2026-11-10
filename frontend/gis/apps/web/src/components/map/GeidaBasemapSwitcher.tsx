import { useEffect, useRef, useState } from "react";
import { GEIDA_BASEMAPS, getGeidaBasemapByStyleUrl, useAppStore } from "@geolibre/core";

/**
 * GEIDA basemap switcher — the same thumbnail button + grid menu the classic
 * Geo-Portal uses. The basemap is the map's background, so it is chosen here
 * rather than listed as a layer in the Layers panel.
 */
export function GeidaBasemapSwitcher() {
  const basemapStyleUrl = useAppStore((s) => s.basemapStyleUrl);
  const setBasemapStyleUrl = useAppStore((s) => s.setBasemapStyleUrl);
  const setBasemapVisible = useAppStore((s) => s.setBasemapVisible);
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const active = getGeidaBasemapByStyleUrl(basemapStyleUrl);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="geida-basemap" data-testid="geida-basemap-switcher">
      <button
        type="button"
        className="geida-basemap-btn"
        aria-haspopup="true"
        aria-expanded={open}
        title="Change basemap"
        onClick={() => setOpen((v) => !v)}
      >
        {active ? <img src={active.thumb} alt="" /> : <span className="geida-basemap-blank" />}
        <span>
          <small>Basemap</small>
          <strong>{active?.name ?? "Custom"}</strong>
        </span>
      </button>
      {open ? (
        <div className="geida-basemap-menu" role="menu">
          {GEIDA_BASEMAPS.map((basemap) => (
            <button
              key={basemap.id}
              type="button"
              role="menuitemradio"
              aria-checked={basemap.styleUrl === basemapStyleUrl}
              className={`geida-bm${basemap.styleUrl === basemapStyleUrl ? " is-on" : ""}`}
              onClick={() => {
                setBasemapStyleUrl(basemap.styleUrl);
                setBasemapVisible(true);
                setOpen(false);
              }}
            >
              <img src={basemap.thumb} alt="" loading="lazy" />
              {basemap.name}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
