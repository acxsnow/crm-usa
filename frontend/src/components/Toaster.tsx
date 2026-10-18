import { useEffect, useState } from "react";
import { dismissToast, subscribeToasts, type Toast } from "@/lib/toast";

/** Muestra los avisos de `toast()`. Se cierran solos o al tocarlos. */
export function Toaster() {
  const [items, setItems] = useState<Toast[]>([]);
  useEffect(() => subscribeToasts(setItems), []);
  return (
    <div className="toaster" role="status" aria-live="polite">
      {items.map((t) => (
        <button key={t.id} type="button" className="toast" onClick={() => dismissToast(t.id)}>
          <span className="toast-check" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="3"
              strokeLinecap="round" strokeLinejoin="round"><path d="M5 12.5l4.5 4.5L19 7.5" /></svg>
          </span>
          {t.message}
        </button>
      ))}
    </div>
  );
}
