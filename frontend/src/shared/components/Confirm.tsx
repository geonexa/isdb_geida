import "@/shared/styles/confirm.css";

import { CircleHelp, TriangleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

export type ConfirmOptions = {
  title: string;
  message?: ReactNode;
  /** Text of the confirming button (default "Continue"). */
  confirmLabel?: string;
  cancelLabel?: string;
  /** "danger" for deletions and other things that can't be undone. */
  tone?: "default" | "danger";
};

type Pending = ConfirmOptions & { resolve: (ok: boolean) => void };

const ConfirmContext = createContext<(o: ConfirmOptions) => Promise<boolean>>(async () => false);

/**
 * GEIDA's replacement for window.confirm: a themed dialog, awaited like a promise.
 *   const confirm = useConfirm();
 *   if (!(await confirm({ title: "Delete the draft?", tone: "danger", confirmLabel: "Delete" }))) return;
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const [pending, setPending] = useState<Pending | null>(null);
  const ask = useCallback((o: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ ...o, resolve })), []);
  const close = (ok: boolean) => { pending?.resolve(ok); setPending(null); };
  return (
    <ConfirmContext.Provider value={ask}>
      {children}
      {pending && <ConfirmDialog {...pending} onClose={close} />}
    </ConfirmContext.Provider>
  );
}

export const useConfirm = () => useContext(ConfirmContext);

function ConfirmDialog({ title, message, confirmLabel = "Continue", cancelLabel = "Cancel", tone = "default", onClose }: ConfirmOptions & { onClose: (ok: boolean) => void }) {
  const okBtn = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    okBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(false); }
      if (e.key === "Tab" && panel.current) {
        // Keep focus inside the dialog.
        const f = [...panel.current.querySelectorAll<HTMLElement>("button")];
        const i = f.indexOf(document.activeElement as HTMLElement);
        if (e.shiftKey && i <= 0) { e.preventDefault(); f[f.length - 1]?.focus(); }
        else if (!e.shiftKey && i === f.length - 1) { e.preventDefault(); f[0]?.focus(); }
      }
    };
    window.addEventListener("keydown", onKey, true);
    return () => { window.removeEventListener("keydown", onKey, true); before?.focus?.(); };
  }, []);
  const Icon = tone === "danger" ? TriangleAlert : CircleHelp;
  return createPortal(
    <div className="cfm-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(false); }}>
      <div ref={panel} className={`cfm cfm-${tone}`} role="alertdialog" aria-modal="true" aria-labelledby="cfm-title" aria-describedby={message ? "cfm-msg" : undefined}>
        <button type="button" className="cfm-x" aria-label="Close" onClick={() => onClose(false)}><X aria-hidden="true" /></button>
        <span className="cfm-icon" aria-hidden="true"><Icon /></span>
        <div className="cfm-text">
          <h2 id="cfm-title">{title}</h2>
          {message && <div id="cfm-msg" className="cfm-msg">{message}</div>}
        </div>
        <div className="cfm-actions">
          <button type="button" className="btn btn-outline btn-sm" onClick={() => onClose(false)}>{cancelLabel}</button>
          <button ref={okBtn} type="button" className={`btn btn-sm ${tone === "danger" ? "cfm-danger" : "btn-dark"}`} onClick={() => onClose(true)}>{confirmLabel}</button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
