import { Search, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

import { api } from "@/shared/api/client";
import type { CRI } from "@/features/projects/types";

/** Type a CRI code or keyword; picking one returns the full CRI record. */
export function CriPicker({ value, onChange }: { value: CRI | null; onChange: (c: CRI | null) => void }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CRI[]>([]);
  const [active, setActive] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const listId = useId();

  useEffect(() => {
    if (!open) return;
    const t = setTimeout(() => {
      api<{ cri: CRI[] }>(`/api/projects/cri/?q=${encodeURIComponent(q)}`).then((d) => { setItems(d.cri); setActive(0); }).catch(() => setItems([]));
    }, 150);
    return () => clearTimeout(t);
  }, [q, open]);
  useEffect(() => {
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (c: CRI) => { onChange(c); setOpen(false); setQ(""); };

  if (value && !open) {
    return (
      <div className="cri-picked">
        <button type="button" className="cri-chip" onClick={() => setOpen(true)} title="Change CRI">
          <strong>{value.code}</strong> {value.name}
        </button>
        <button type="button" className="icon-btn" aria-label="Remove CRI (project-specific indicator)" onClick={() => onChange(null)}><X aria-hidden="true" /></button>
      </div>
    );
  }
  return (
    <div className="cri-picker" ref={ref}>
      <label className="psearch">
        <Search aria-hidden="true" />
        <input value={q} placeholder="CRI code or keyword, e.g. 3.2 or irrigat" autoFocus={open && !!value}
               role="combobox" aria-expanded={open} aria-controls={listId} aria-label="Core Result Indicator"
               onFocus={() => setOpen(true)} onChange={(e) => { setQ(e.target.value); setOpen(true); }}
               onKeyDown={(e) => {
                 if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
                 if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
                 if (e.key === "Enter" && items[active]) { e.preventDefault(); pick(items[active]); }
                 if (e.key === "Escape") setOpen(false);
               }} />
      </label>
      {open && (
        <ul className="cri-list" id={listId} role="listbox">
          {items.length === 0 && <li className="muted">No CRI matches. Leave blank for a project-specific indicator.</li>}
          {items.map((c, i) => (
            <li key={c.code} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(c); }} onMouseEnter={() => setActive(i)}>
              <strong>{c.code}</strong>
              <span>{c.name}<em>{c.unit || "no unit"} · {c.group_name}{c.geida_role !== "none" ? ` · GEIDA: ${c.geida_role}` : ""}</em></span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
