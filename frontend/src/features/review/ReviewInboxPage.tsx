import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "@/features/auth/AuthContext";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { DocumentsQueue } from "@/features/sales/DocumentsQueuePage";
import { docKeys, type QueueRow } from "@/features/sales/api";
import { ActaReviewQueue, type PendingReviewRow } from "@/features/field-ops/ActaReviewQueuePage";

import "../billing/billing.css";
import "../sales/sales.css";

export type QueueList<T> = ReturnType<typeof usePaginatedQuery<T>>;

interface InspectionRow {
  project_id: string; case_id: string | null; case_number: string | null; title: string;
  customer_name: string | null; completed_date: string | null;
  status: "unscheduled" | "scheduled" | "failed"; scheduled_for: string | null; days_since_close: number | null;
}

interface ToCreateRow {
  project_id: string; case_id: string | null; case_number: string | null; customer_name: string | null;
  address: string | null; confirmed_on: string; installation_date: string | null; days: number;
}

const TABS = [
  { key: "documentos", label: "Documentos", permission: "documents.review" },
  { key: "actas", label: "Actas por confirmar", permission: "checklists.approve" },
  { key: "inspecciones", label: "Inspección municipal", permission: "inspections.manage" },
  { key: "cobros", label: "Cobros por crear", permission: "billing.submit" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

/** Permisos que abren la bandeja: el menú y la ruta usan la misma lista. */
export const REVIEW_INBOX_PERMISSIONS = TABS.map((t) => t.permission);

const LEAD: Record<TabKey, string> = {
  documentos: "Expedientes enviados con documentos pendientes o rechazados. Los que más llevan esperando, primero.",
  actas: "Instalaciones cerradas por el técnico que esperan la revisión de Administración.",
  inspecciones: "Instalaciones cerradas sin inspección municipal aprobada: por agendar, agendadas o por reagendar.",
  cobros: "Actas confirmadas que todavía no tienen cobro al programa. Radicar y registrar pagos sigue en Facturación.",
};

const dia = (iso: string) => new Date(iso.length === 10 ? `${iso}T12:00:00` : iso)
  .toLocaleDateString("es-CO", { day: "numeric", month: "short" });
const dias = (n: number) => (n === 0 ? "Hoy" : n === 1 ? "1 día" : `${n} días`);

/**
 * «Por revisar» (spec 2026-10-19-bandeja-por-revisar): el trabajo diario de
 * Administración en un solo lugar. Cada pestaña se ve con su permiso y lleva
 * su número; cada fila abre el expediente o el proyecto en el paso que toca.
 */
export function ReviewInboxPage() {
  const { hasPermission } = useAuth();
  const [params, setParams] = useSearchParams();
  const visibles = TABS.filter((t) => hasPermission(t.permission));
  const tab: TabKey = visibles.find((t) => t.key === params.get("tab"))?.key ?? visibles[0]?.key ?? "documentos";

  const listas = {
    documentos: usePaginatedQuery<QueueRow>({ key: docKeys.queue, path: "/documents/review-queue",
      enabled: hasPermission("documents.review") }),
    actas: usePaginatedQuery<PendingReviewRow>({ key: ["acta-reviews"], path: "/acta-reviews/pending",
      enabled: hasPermission("checklists.approve") }),
    inspecciones: usePaginatedQuery<InspectionRow>({ key: ["inspection-queue"], path: "/inspection-queue",
      enabled: hasPermission("inspections.manage") }),
    cobros: usePaginatedQuery<ToCreateRow>({ key: ["billing-to-create"], path: "/billing/to-create",
      enabled: hasPermission("billing.submit") }),
  };

  return (
    <div className="billing-page">
      <header className="billing-head">
        <div>
          <h1>Por revisar</h1>
          <p>{LEAD[tab]}</p>
        </div>
      </header>
      {visibles.length > 1 && (
        <nav className="billing-tabs" role="tablist" aria-label="Bandejas por revisar">
          {visibles.map((t) => (
            <button key={t.key} type="button" role="tab" aria-selected={tab === t.key}
              className={`billing-tab${tab === t.key ? " is-active" : ""}`}
              onClick={() => setParams(t.key === visibles[0].key ? {} : { tab: t.key })}>
              {t.label}
              {listas[t.key].total > 0 && <span className="billing-count">{listas[t.key].total}</span>}
            </button>
          ))}
        </nav>
      )}
      {tab === "documentos" && <DocumentsQueue lista={listas.documentos} />}
      {tab === "actas" && <ActaReviewQueue lista={listas.actas} />}
      {tab === "inspecciones" && <InspectionQueue lista={listas.inspecciones} />}
      {tab === "cobros" && <ClaimsToCreate lista={listas.cobros} />}
    </div>
  );
}

const ESTADO_INSPECCION: Record<InspectionRow["status"], { label: string; chip: string }> = {
  unscheduled: { label: "Sin agendar", chip: "is-rejected" },
  failed: { label: "Falló: reagendar", chip: "is-rejected" },
  scheduled: { label: "Agendada", chip: "is-preparing" },
};

function InspectionQueue({ lista }: { lista: QueueList<InspectionRow> }) {
  const { items, isLoading } = lista;
  return (
    <article className="acta">
      {isLoading ? <p className="acta-empty">Cargando…</p> : items.length === 0 ? (
        <p className="acta-empty">Todas las instalaciones cerradas tienen su inspección aprobada.</p>
      ) : (
        <ul className="sales-cases queue-list">
          {items.map((r) => {
            const estado = ESTADO_INSPECCION[r.status];
            return (
              <li key={r.project_id}>
                <Link to={`/projects/${r.project_id}?paso=inspection`}
                  state={{ backTo: "/review?tab=inspecciones", backLabel: "Por revisar" }}>
                  <span>
                    <strong>{r.customer_name ?? r.title}</strong>
                    <small>
                      {r.case_number ?? r.title}
                      {r.completed_date && ` · cerrada el ${dia(r.completed_date)}`}
                      {r.status === "scheduled" && r.scheduled_for && ` · inspección el ${dia(r.scheduled_for)}`}
                    </small>
                  </span>
                  <span className="queue-counts">
                    <span className={`billing-chip ${estado.chip}`}>{estado.label}</span>
                    {r.days_since_close !== null && <span className="billing-chip">⏱ {dias(r.days_since_close)}</span>}
                    <span aria-hidden="true">›</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}

function ClaimsToCreate({ lista }: { lista: QueueList<ToCreateRow> }) {
  const { items, isLoading } = lista;
  return (
    <article className="acta">
      {isLoading ? <p className="acta-empty">Cargando…</p> : items.length === 0 ? (
        <p className="acta-empty">No hay cobros por crear. Aparecen cuando Administración confirma un acta.</p>
      ) : (
        <ul className="sales-cases queue-list">
          {items.map((r) => (
            <li key={r.project_id}>
              <Link to={`/projects/${r.project_id}?paso=billing`}
                state={{ backTo: "/review?tab=cobros", backLabel: "Por revisar" }}>
                <span>
                  <strong>{r.customer_name ?? r.case_number ?? "Instalación"}</strong>
                  <small>
                    {r.case_number ?? ""}
                    {r.address && ` · ${r.address}`}
                    {` · acta confirmada el ${dia(r.confirmed_on)}`}
                  </small>
                </span>
                <span className="queue-counts">
                  <span className={`billing-chip ${r.days >= 1 ? "is-rejected" : "is-preparing"}`}>⏱ {dias(r.days)}</span>
                  <span aria-hidden="true">›</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <PaginationControls {...lista.controls} />
      <p className="acta-hint">
        Para radicar, ver rechazos y registrar pagos: <Link to="/invoices">Facturación y cobros</Link>.
      </p>
    </article>
  );
}
