import { useEffect, useRef, useState } from "react";

/**
 * Confirmaciones sin `window.confirm`/`window.prompt` (propuesta UI/UX V1): un
 * diálogo propio que dice el impacto de la acción, con foco atrapado, Escape
 * para cancelar y, en el celular, como hoja desde abajo.
 *
 *   const ok = await confirmAction({ title: "¿Borrar este gasto?", danger: true });
 *   const motivo = await askText({ title: "Motivo de la anulación", required: true });
 *
 * Vive fuera de React (como `toast`): `<ConfirmHost />` va una sola vez en
 * `providers.tsx`.
 */
interface Pedido {
  title: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  /** Con `input`, el diálogo pide un texto y devuelve lo escrito (o null). */
  input?: { label: string; required?: boolean; placeholder?: string };
  resolve: (valor: boolean | string | null) => void;
}

let actual: Pedido | null = null;
const oyentes = new Set<(p: Pedido | null) => void>();
const avisar = () => oyentes.forEach((o) => o(actual));

function pedir(p: Omit<Pedido, "resolve">): Promise<boolean | string | null> {
  return new Promise((resolve) => {
    actual?.resolve(actual.input ? null : false);
    actual = { ...p, resolve };
    avisar();
  });
}

export function confirmAction(p: Omit<Pedido, "resolve" | "input">): Promise<boolean> {
  return pedir(p) as Promise<boolean>;
}

export function askText(p: Omit<Pedido, "resolve" | "input"> & { label?: string; required?: boolean; placeholder?: string }): Promise<string | null> {
  const { label = p.title, required, placeholder, ...resto } = p;
  return pedir({ ...resto, input: { label, required, placeholder } }) as Promise<string | null>;
}

export function ConfirmHost() {
  const [pedido, setPedido] = useState<Pedido | null>(null);
  const [texto, setTexto] = useState("");
  const caja = useRef<HTMLDivElement>(null);
  const previo = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const oyente = (p: Pedido | null) => setPedido(p);
    oyentes.add(oyente);
    return () => { oyentes.delete(oyente); };
  }, []);

  const cerrar = (valor: boolean | string | null) => {
    if (!actual) return;
    const p = actual;
    actual = null;
    setTexto("");
    avisar();
    p.resolve(valor);
    previo.current?.focus();
  };

  useEffect(() => {
    if (!pedido) return;
    previo.current = document.activeElement as HTMLElement | null;
    const primero = caja.current?.querySelector<HTMLElement>("input, button");
    primero?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") cerrar(pedido.input ? null : false);
      if (e.key !== "Tab" || !caja.current) return;
      const focos = Array.from(caja.current.querySelectorAll<HTMLElement>("input, button:not(:disabled)"));
      if (!focos.length) return;
      const [a, z] = [focos[0], focos[focos.length - 1]];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pedido]);

  if (!pedido) return null;
  const falta = Boolean(pedido.input?.required && !texto.trim());
  return (
    <div className="ui-dialog-backdrop" onClick={(e) => { if (e.target === e.currentTarget) cerrar(pedido.input ? null : false); }}>
      <div ref={caja} className="ui-dialog" role="alertdialog" aria-modal="true" aria-labelledby="ui-dialog-title">
        <h2 id="ui-dialog-title">{pedido.title}</h2>
        {pedido.message && <p>{pedido.message}</p>}
        <form onSubmit={(e) => { e.preventDefault(); if (!falta) cerrar(pedido.input ? texto.trim() : true); }}>
          {pedido.input && (
            <label>
              {pedido.input.label}
              <input value={texto} placeholder={pedido.input.placeholder} onChange={(e) => setTexto(e.target.value)} />
            </label>
          )}
          <div className="ui-dialog-actions">
            <button type="button" className="acta-btn" onClick={() => cerrar(pedido.input ? null : false)}>
              {pedido.cancelLabel ?? "Cancelar"}
            </button>
            <button type="submit" className={`acta-btn is-primary${pedido.danger ? " is-danger" : ""}`} disabled={falta}>
              {pedido.confirmLabel ?? "Confirmar"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
