import { useState } from "react";
import { Link } from "react-router-dom";

import "../billing/billing.css";
import "../notifications/notifications.css";
import "./finance.css";
import { PaginatedTable } from "@/components/DataTable";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import type { InspectionRow, PermitRow } from "./api";
import { Tabs, fecha } from "./common";

type Tab = "permits" | "inspections";
const PERMISO: Record<string, string> = { in_process: "is-preparing", submitted: "is-preparing", approved: "is-accepted", rejected: "is-rejected", not_required: "is-void" };
const INSPECCION: Record<string, string> = { pending: "is-submitted", passed: "is-accepted", failed: "is-rejected" };

/**
 * Permisos e inspecciones de todos los proyectos, para ver de un vistazo qué
 * vence y qué inspección viene. Se registran en el proyecto (acta).
 */
export function PermitsPage() {
  const [tab, setTab] = useState<Tab>("permits");
  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Permisos e inspecciones</h1>
          <p>Los permisos municipales y las inspecciones de todas las instalaciones. Se registran dentro de cada proyecto.</p>
        </div>
      </header>
      <Tabs tabs={[["permits", "Permisos"], ["inspections", "Inspecciones"]]} value={tab} onChange={setTab} />
      {tab === "permits" ? <Permits /> : <Inspections />}
    </div>
  );
}

function Permits() {
  const [filtro, setFiltro] = useState("expiring");
  const params = filtro === "expiring" ? { expiring_within_days: 30 } : { status: filtro || undefined };
  const lista = usePaginatedQuery<PermitRow>({ key: ["all-permits"], path: "/permits", pageSize: 25, params });
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <select aria-label="Filtro" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
          <option value="expiring">Vencen en 30 días</option><option value="in_process">En trámite</option><option value="submitted">Radicados</option>
          <option value="approved">Aprobados</option><option value="rejected">Rechazados</option>
          <option value="not_required">No requeridos</option><option value="">Todos</option>
        </select>
      </div>
      <PaginatedTable list={lista} getRowKey={(p) => p.id} emptyMessage="Ningún permiso con este filtro."
        rowClassName={(p) => (p.days_to_expiry !== null && p.days_to_expiry <= 7 && p.days_to_expiry >= 0 ? "fin-overdue" : undefined)}
        columns={[
          { key: "proyecto", header: "Proyecto", render: (p) => <Link to={`/projects/${p.project_id}`} className="acta-link"><strong>{p.project_title}</strong></Link> },
          { key: "permiso", header: "Permiso", render: (p) => <>{p.jurisdiction}<small>{[p.permit_type, p.permit_number].filter(Boolean).join(" · ")}</small></> },
          { key: "estado", header: "Estado", render: (p) => (
            <>
              <span className={`billing-chip ${PERMISO[p.status] ?? ""}`}>{p.status_label}</span>
              {p.filed_on && <small>radicado {fecha(p.filed_on)}</small>}
            </>
          ) },
          { key: "vence", header: "Vence", render: (p) => (
            <>
              {fecha(p.expires_on)}
              {p.days_to_expiry !== null && <small>{p.days_to_expiry < 0 ? `venció hace ${-p.days_to_expiry} días` : `en ${p.days_to_expiry} días`}</small>}
            </>
          ) },
        ]} />
    </article>
  );
}

function Inspections() {
  const [filtro, setFiltro] = useState("upcoming");
  const params = filtro === "upcoming" ? { upcoming: true } : { result: filtro || undefined };
  const lista = usePaginatedQuery<InspectionRow>({ key: ["all-inspections"], path: "/inspections", pageSize: 25, params });
  return (
    <article className="acta">
      <div className="notices-toolbar">
        <select aria-label="Filtro" value={filtro} onChange={(e) => setFiltro(e.target.value)}>
          <option value="upcoming">Próximas</option><option value="failed">Fallidas</option>
          <option value="passed">Aprobadas</option><option value="">Todas</option>
        </select>
      </div>
      <PaginatedTable list={lista} getRowKey={(i) => i.id} emptyMessage="Ninguna inspección con este filtro."
        columns={[
          { key: "proyecto", header: "Proyecto", render: (i) => <Link to={`/projects/${i.project_id}`} className="acta-link"><strong>{i.project_title}</strong></Link> },
          { key: "fecha", header: "Fecha", render: (i) => new Date(i.scheduled_for).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" }) },
          { key: "inspector", header: "Inspector", render: (i) => i.inspector_name ?? "—" },
          { key: "resultado", header: "Resultado", render: (i) => (
            <>
              <span className={`billing-chip ${INSPECCION[i.result] ?? ""}`}>{i.result_label}</span>
              {i.observations && <small>{i.observations}</small>}
            </>
          ) },
        ]} />
    </article>
  );
}
