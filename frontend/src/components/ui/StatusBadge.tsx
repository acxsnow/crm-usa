import type { ReactNode } from "react";

/**
 * Chip de estado con semántica uniforme (propuesta UI/UX V1): no todo en rojo.
 * - `ok`: aprobado, pagado, completado, activo.
 * - `warn`: pendiente, por revisar, borrador.
 * - `info`: en progreso, agendado, enviado.
 * - `danger`: rechazado, vencido, atrasado.
 * - `neutral`: cerrado, cancelado, inactivo.
 */
export type StatusTone = "ok" | "warn" | "info" | "danger" | "neutral";

export function StatusBadge({ tone = "neutral", children }: { tone?: StatusTone; children: ReactNode }) {
  return <span className={`ui-status is-${tone}`}>{children}</span>;
}
