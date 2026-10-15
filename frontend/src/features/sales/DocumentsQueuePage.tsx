import { Link } from "react-router-dom";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";

import "../billing/billing.css";
import "./sales.css";
import { SUBSTATUS_LABELS } from "./CaseReviewPage";
import { ApprovalDays } from "./ApprovalDays";
import { docKeys, type QueueRow } from "./api";

/**
 * Documentos por revisar (módulo 3): los expedientes en revisión que tienen
 * algo pendiente o rechazado, los que más llevan esperando primero.
 */
export function DocumentsQueuePage() {
  const lista = usePaginatedQuery<QueueRow>({ key: docKeys.queue, path: "/documents/review-queue", pageSize: 20 });
  const { items: data, isLoading } = lista;
  return (
    <div className="billing-page">
      <header className="billing-head">
        <div>
          <h1>Documentos por revisar</h1>
          <p>Expedientes enviados con documentos pendientes o rechazados. Los que más llevan esperando, primero.</p>
        </div>
      </header>
      <article className="acta">
        {isLoading ? <p className="acta-empty">Cargando…</p> : data.length === 0 ? (
          <p className="acta-empty">Todo revisado. Cuando un vendedor envíe un expediente, sus documentos aparecen aquí.</p>
        ) : (
          <ul className="sales-cases queue-list">
            {data.map((r) => (
              <li key={r.case_id}>
                <Link to={`/cases/${r.case_id}/review`}>
                  <span>
                    <strong>{r.customer_name ?? r.case_number}</strong>
                    <small>
                      {r.case_number}{r.program_name ? ` · ${r.program_name}` : ""}
                      {r.substatus_code && SUBSTATUS_LABELS[r.substatus_code] ? ` · ${SUBSTATUS_LABELS[r.substatus_code]}` : ` · ${r.stage_label}`}
                      {r.submitted_at && ` · enviado ${new Date(r.submitted_at).toLocaleDateString("es-CO", { dateStyle: "medium" })}`}
                    </small>
                  </span>
                  <span className="queue-counts">
                    <ApprovalDays wait={r.approval_wait} />
                    {r.pending > 0 && <span className="billing-chip is-preparing">{r.pending} por revisar</span>}
                    {r.rejected > 0 && <span className="billing-chip is-rejected">{r.rejected} rechazados</span>}
                    <span className="billing-chip is-accepted">{r.accepted} aceptados</span>
                    <span aria-hidden="true">›</span>
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </div>
  );
}
