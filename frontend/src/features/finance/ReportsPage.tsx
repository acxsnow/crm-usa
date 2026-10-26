import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../notifications/notifications.css";
import "./finance.css";
import { useAuth } from "@/features/auth/AuthContext";
import { downloadFile, getReport } from "./api";
import { Tabs, fecha } from "./common";

type Kind = "commercial" | "operations" | "finance";
/** El permiso de cada reporte (D-014): el comercial es del tablero comercial; los otros, de «Generar reportes». */
const REPORTES: [Kind, string, string][] = [
  ["commercial", "Comercial", "dashboards.commercial"],
  ["operations", "Operación", "reports.generate"],
  ["finance", "Finanzas", "reports.generate"],
];
const hace = (dias: number) => new Date(Date.now() - dias * 86400000).toLocaleDateString("en-CA");

/** Reportes de gestión: comercial, operación y finanzas, con exportación a CSV. */
export function ReportsPage() {
  const { hasPermission } = useAuth();
  const visibles = REPORTES.filter(([, , permiso]) => hasPermission(permiso));
  const [elegido, setKind] = useState<Kind | null>(null);
  const kind: Kind | null = elegido ?? visibles[0]?.[0] ?? null;
  const [desde, setDesde] = useState(hace(30));
  const [hasta, setHasta] = useState(new Date().toLocaleDateString("en-CA"));
  const { data, isLoading } = useQuery({
    queryKey: ["report", kind, desde, hasta], enabled: kind !== null,
    queryFn: () => getReport(kind as Kind, { date_from: desde, date_to: hasta }),
  });
  const rapido = (dias: number) => { setDesde(hace(dias)); setHasta(new Date().toLocaleDateString("en-CA")); };
  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Reportes</h1>
          <p>Cómo va la venta, la operación de campo y el dinero, con los datos registrados.</p>
        </div>
        {hasPermission("reports.export") && kind && (
          <div className="acta-actions"><button type="button" className="acta-btn is-quiet"
            onClick={() => downloadFile(`/reports/${kind}/csv`, `reporte-${kind}-${desde}-${hasta}.csv`, { date_from: desde, date_to: hasta })}>Exportar CSV</button></div>
        )}
      </header>
      {kind === null ? (
        <p className="acta-empty">Tu rol no tiene ningún reporte asignado. Pídele al Administrador que te dé el comercial o «Generar reportes».</p>
      ) : (
        <Tabs tabs={visibles.map(([k, l]) => [k, l] as [Kind, string])} value={kind} onChange={setKind} />
      )}
      {kind !== null && (
      <article className="acta">
        <div className="notices-toolbar fin-filters">
          <label className="notices-hint">Desde <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
          <label className="notices-hint">hasta <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
          <div className="acta-actions">
            {[[7, "7 días"], [30, "30 días"], [90, "90 días"], [365, "1 año"]].map(([d, l]) => (
              <button key={d} type="button" className="acta-link" onClick={() => rapido(d as number)}>{l}</button>))}
          </div>
        </div>
        {isLoading || !data ? <p className="acta-empty">Cargando…</p> : (
          <>
            <p className="notices-hint">{fecha(data.range[0])} a {fecha(data.range[1])}</p>
            <div className="fin-kpis">
              {data.kpis.map((k) => <div key={k.label} className="fin-kpi"><small>{k.label}</small>
                <strong>{k.value === null || k.value === undefined ? "—" : /^-?\d+\.\d{2}$/.test(String(k.value)) ? `$${Number(k.value).toLocaleString("en-US", { minimumFractionDigits: 2 })}` : k.value}</strong></div>)}
            </div>
            {data.sections.map((s) => (
              <section key={s.title} className="fin-section">
                <h2 className="fin-h2">{s.title}</h2>
                {s.rows.length === 0 ? <p className="acta-empty">Sin datos en el periodo.</p> : (
                  <div className="tablewrap"><table className="notices-table">
                    <thead><tr>{s.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                    <tbody>{s.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={j > 0 ? "mono" : ""}>{c}</td>)}</tr>)}</tbody>
                  </table></div>
                )}
              </section>
            ))}
          </>
        )}
      </article>
      )}
    </div>
  );
}
