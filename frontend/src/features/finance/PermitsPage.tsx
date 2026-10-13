import { useState } from "react";
import { Link } from "react-router-dom";

import "../billing/billing.css";
import "../notifications/notifications.css";
import "./finance.css";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import type { InspectionRow, PermitRow } from "./api";
import { Tabs, fecha } from "./common";

type Tab = "permits" | "inspections";
const PERMISO: Record<string, string> = { submitted: "is-preparing", approved: "is-accepted", rejected: "is-rejected", not_required: "is-void" };
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
          <option value="expiring">Vencen en 30 días</option><option value="submitted">Radicados (en trámite)</option>
          <option value="approved">Aprobados</option><option value="rejected">Rechazados</option>
          <option value="not_required">No requeridos</option><option value="">Todos</option>
        </select>
      </div>
      {lista.items.length === 0 ? <p className="acta-empty">Ningún permiso con este filtro.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Proyecto</th><th>Permiso</th><th>Estado</th><th>Vence</th></tr></thead>
          <tbody>{lista.items.map((p) => (
            <tr key={p.id} className={p.days_to_expiry !== null && p.days_to_expiry <= 7 && p.days_to_expiry >= 0 ? "fin-overdue" : ""}>
              <td><Link to={`/projects/${p.project_id}`} className="acta-link"><strong>{p.project_title}</strong></Link></td>
              <td>{p.jurisdiction}<small>{[p.permit_type, p.permit_number].filter(Boolean).join(" · ")}</small></td>
              <td><span className={`billing-chip ${PERMISO[p.status] ?? ""}`}>{p.status_label}</span>
                {p.filed_on && <small>radicado {fecha(p.filed_on)}</small>}</td>
              <td>{fecha(p.expires_on)}{p.days_to_expiry !== null && <small>{p.days_to_expiry < 0 ? `venció hace ${-p.days_to_expiry} días` : `en ${p.days_to_expiry} días`}</small>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
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
      {lista.items.length === 0 ? <p className="acta-empty">Ninguna inspección con este filtro.</p> : (
        <div className="tablewrap"><table className="notices-table">
          <thead><tr><th>Proyecto</th><th>Fecha</th><th>Inspector</th><th>Resultado</th></tr></thead>
          <tbody>{lista.items.map((i) => (
            <tr key={i.id}>
              <td><Link to={`/projects/${i.project_id}`} className="acta-link"><strong>{i.project_title}</strong></Link></td>
              <td>{new Date(i.scheduled_for).toLocaleString("es-CO", { dateStyle: "medium", timeStyle: "short" })}</td>
              <td>{i.inspector_name ?? "—"}</td>
              <td><span className={`billing-chip ${INSPECCION[i.result] ?? ""}`}>{i.result_label}</span>
                {i.observations && <small>{i.observations}</small>}</td>
            </tr>
          ))}</tbody>
        </table></div>
      )}
      <PaginationControls {...lista.controls} />
    </article>
  );
}
