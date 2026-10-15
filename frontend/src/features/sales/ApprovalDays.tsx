import type { ApprovalWait } from "./api";

/**
 * Días hábiles que lleva un expediente esperando aprobación (spec
 * 2026-10-14-contador-dias-aprobacion). El servidor manda el cálculo —la misma
 * regla de la alerta diaria— y el límite, así que aquí solo se pinta: gris
 * mientras está a tiempo, rojo desde el límite. Sin dato no pinta nada.
 */
export function ApprovalDays({ wait }: { wait?: ApprovalWait | null }) {
  if (!wait) return null;
  const n = wait.business_days;
  const texto = n === 0 ? "Enviado hoy" : `${n} ${n === 1 ? "día hábil" : "días hábiles"}`;
  return (
    <span className={`approval-days${wait.overdue ? " is-overdue" : ""}`}
      title={`Días hábiles desde que se envió a revisión. Límite: ${wait.limit}.`}>
      <span aria-hidden="true">⏱</span> {texto}{wait.overdue ? ` · límite ${wait.limit}` : ""}
    </span>
  );
}
