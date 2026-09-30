import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import "./billing.css";
import { useAuth } from "@/features/auth/AuthContext";
import { billingKeys, getBillingDashboard } from "./billingApi";
import { ClaimsInbox } from "./ClaimsInbox";
import { InvoicesTab } from "./InvoicesTab";
import { ProgramsConfigTab } from "./ProgramsConfigTab";
import { QuotesTab } from "./QuotesTab";

const TABS = [
  { key: "claims", label: "Cobros de programas" },
  { key: "invoices", label: "Facturas" },
  { key: "quotes", label: "Cotizaciones", permission: "quotes.manage" },
  { key: "programs", label: "Programas" },
] as const;

/**
 * Facturación y cobro (módulo 6). Entrada del menú: la bandeja de cobros a
 * los programas; al lado, todas las facturas, las cotizaciones de trabajo
 * particular y la configuración de cada programa.
 */
export function InvoicesPage() {
  const [params, setParams] = useSearchParams();
  const { hasPermission } = useAuth();
  const tabs = TABS.filter((t) => !("permission" in t) || hasPermission(t.permission));
  const tab = tabs.find((t) => t.key === params.get("tab"))?.key ?? "claims";
  const { data: tablero } = useQuery({ queryKey: billingKeys.dashboard, queryFn: getBillingDashboard });
  const pendientes = tablero
    ? tablero.to_create.length + tablero.to_submit.length + tablero.rejected.length
    : 0;

  return (
    <div className="billing-page">
      <header className="billing-head">
        <h1>Facturación y cobro</h1>
        <p>Cobro a los programas por cada instalación y trabajo particular que paga el cliente.</p>
      </header>
      <nav className="billing-tabs" role="tablist" aria-label="Secciones de facturación">
        {tabs.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key}
            className={`billing-tab${tab === t.key ? " is-active" : ""}`}
            onClick={() => setParams(t.key === "claims" ? {} : { tab: t.key })}>
            {t.label}
            {t.key === "claims" && pendientes > 0 && <span className="billing-count">{pendientes}</span>}
          </button>
        ))}
      </nav>
      {tab === "claims" && <ClaimsInbox />}
      {tab === "invoices" && <InvoicesTab />}
      {tab === "quotes" && <QuotesTab />}
      {tab === "programs" && <ProgramsConfigTab />}
    </div>
  );
}
