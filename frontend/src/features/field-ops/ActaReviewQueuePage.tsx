import { Link } from "react-router-dom";
import { PaginationControls } from "@/components/PaginationControls";
import type { QueueList } from "@/features/review/ReviewInboxPage";

import "../billing/billing.css";
import "../sales/sales.css";

export interface PendingReviewRow {
  project_id: string;
  case_id: string | null;
  case_number: string | null;
  title: string;
  customer_name: string | null;
  technician_name: string | null;
  completed_date: string | null;
  days_waiting: number | null;
}

const fecha = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

/**
 * Actas por confirmar (spec 2026-10-19-actas-por-confirmar): las instalaciones
 * que el técnico cerró y esperan a Administración, la más vieja primero. Cada
 * fila abre el proyecto directo en el paso «Confirmación de Administración».
 * Es la pestaña «Actas por confirmar» de la bandeja «Por revisar».
 */
export function ActaReviewQueue({ lista }: { lista: QueueList<PendingReviewRow> }) {
  const { items: data, isLoading } = lista;
  return (
    <article className="acta">
      {isLoading ? <p className="acta-empty">Cargando…</p> : data.length === 0 ? (
        <p className="acta-empty">Nada por confirmar. Cuando un técnico cierre una instalación, su acta aparece aquí.</p>
      ) : (
        <ul className="sales-cases queue-list">
          {data.map((r) => (
            <li key={r.project_id}>
              <Link to={`/projects/${r.project_id}?paso=review`}
                state={{ backTo: "/review?tab=actas", backLabel: "Por revisar" }}>
                <span>
                  <strong>{r.customer_name ?? r.title}</strong>
                  <small>
                    {r.case_number ?? r.title}
                    {r.technician_name && ` · ${r.technician_name}`}
                    {r.completed_date && ` · cerrada el ${fecha(r.completed_date)}`}
                  </small>
                </span>
                <span className="queue-counts">
                  {r.days_waiting !== null && (
                    <span className={`billing-chip ${r.days_waiting >= 3 ? "is-rejected" : "is-preparing"}`}>
                      ⏱ {r.days_waiting === 0 ? "Hoy" : r.days_waiting === 1 ? "1 día" : `${r.days_waiting} días`}
                    </span>
                  )}
                  <span aria-hidden="true">›</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}
