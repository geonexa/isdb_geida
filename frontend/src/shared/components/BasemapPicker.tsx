import "@/shared/styles/basemap.css";

import { useEffect, useId, useRef, useState } from "react";

import type { Basemap } from "@/shared/map/basemaps";

type Props = {
  basemaps: Basemap[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
};

/** Basemap picker in the Geo-Portal's style: current basemap as a thumbnail button, the rest in a grid. */
export function BasemapPicker({ basemaps, value, onChange, className }: Props) {
  const [open, setOpen] = useState(false);
  const wrap = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const current = basemaps.find((b) => b.id === value) ?? basemaps[0];

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => { if (!wrap.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onClick); document.removeEventListener("keydown", onKey); };
  }, [open]);

  if (!current) return null;
  return (
    <div className={`bmp ${className ?? ""}`} ref={wrap}>
      <button type="button" className="bmp-btn" aria-expanded={open} aria-controls={menuId} onClick={() => setOpen(!open)}>
        <img src={current.thumb} alt="" />
        <span><small>Basemap</small><strong>{current.name}</strong></span>
      </button>
      <div className={`bmp-menu${open ? " is-open" : ""}`} id={menuId} role="radiogroup" aria-label="Basemap">
        {basemaps.map((b) => (
          <button key={b.id} type="button" role="radio" aria-checked={b.id === current.id}
            className={`bmp-opt${b.id === current.id ? " is-on" : ""}`}
            onClick={() => { onChange(b.id); setOpen(false); }}>
            <img src={b.thumb} alt="" loading="lazy" />
            <span>{b.name}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
