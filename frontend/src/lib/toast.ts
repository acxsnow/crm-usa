/**
 * Avisos cortos de «guardado» comunes a toda la app (spec
 * 2026-10-18-guardar-equipos-y-avisos). Vive fuera de React para que el
 * `MutationCache` de React Query, que se crea antes del árbol, pueda avisar.
 */
export type Toast = { id: number; message: string };
type Listener = (toasts: Toast[]) => void;

const DURACION_MS = 3500;
let toasts: Toast[] = [];
let siguiente = 1;
const listeners = new Set<Listener>();

function emitir() {
  listeners.forEach((l) => l(toasts));
}

export function dismissToast(id: number) {
  toasts = toasts.filter((t) => t.id !== id);
  emitir();
}

export function toast(message: string) {
  const id = siguiente++;
  // Como mucho tres a la vez: el más viejo sale primero.
  toasts = [...toasts.slice(-2), { id, message }];
  emitir();
  window.setTimeout(() => dismissToast(id), DURACION_MS);
}

export function subscribeToasts(listener: Listener): () => void {
  listeners.add(listener);
  listener(toasts);
  return () => { listeners.delete(listener); };
}
