import { CircleAlert, CircleCheck, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";

type Kind = "success" | "error" | "info";
type Toast = { id: number; kind: Kind; text: string };

const ToastContext = createContext<(text: string, kind?: Kind) => void>(() => {});

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const seq = useRef(0);
  const dismiss = useCallback((id: number) => setToasts((t) => t.filter((x) => x.id !== id)), []);
  const push = useCallback((text: string, kind: Kind = "info") => {
    const id = ++seq.current;
    setToasts((t) => [...t, { id, kind, text }]);
    if (kind !== "error") setTimeout(() => dismiss(id), 6000);
  }, [dismiss]);
  // Plain-JS code (the Geo-Portal engine) shows toasts with
  // window.dispatchEvent(new CustomEvent("geida:toast", { detail: { text, kind } })).
  useEffect(() => {
    const on = (e: Event) => { const d = (e as CustomEvent<{ text: string; kind?: Kind }>).detail; if (d?.text) push(d.text, d.kind ?? "info"); };
    window.addEventListener("geida:toast", on);
    return () => window.removeEventListener("geida:toast", on);
  }, [push]);
  const Icon = { success: CircleCheck, error: CircleAlert, info: Info };
  return (
    <ToastContext.Provider value={push}>
      {children}
      {toasts.length > 0 && (
        <div className="toasts" role="status" aria-live="polite">
          {toasts.map((t) => {
            const I = Icon[t.kind];
            return (
              <div key={t.id} className={`toast toast-${t.kind}`}>
                <I aria-hidden="true" />
                <span>{t.text}</span>
                <button type="button" className="toast-close" aria-label="Dismiss" onClick={() => dismiss(t.id)}>
                  <X aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </ToastContext.Provider>
  );
}

export const useToast = () => useContext(ToastContext);
