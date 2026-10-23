import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./sales.css";
import { useAuth } from "@/features/auth/AuthContext";
import { getBoard, myPrograms, salesKeys } from "./api";
import { Icon } from "@/components/ui/Icon";
import { Avatar } from "@/components/ui/Avatar";

/**
 * Inicio del vendedor (módulo 2, D5): sus programas y zonas, el botón para
 * tocar una puerta y lo que tiene pendiente (sin enviar o devuelto).
 */
export function SalesHomePage() {
  const { user } = useAuth();
  const { data: mios } = useQuery({ queryKey: salesKeys.mine, queryFn: myPrograms });
  const { data: tablero } = useQuery({ queryKey: salesKeys.board(false, true), queryFn: () => getBoard(false, true) });
  const prospectos = tablero?.find((c) => c.code === "new_prospect")?.cases ?? [];
  const devueltos = (tablero?.find((c) => c.code === "pending_approval")?.cases ?? []).filter((c) => c.substatus_code === "returned");
  const enviados = tablero?.find((c) => c.code === "pending_approval")?.count ?? 0;

  return (
    <div className="sales-page">
      <header className="sales-hello">
        <p>Hola, {user?.full_name?.split(" ")[0] ?? "vendedor"}</p>
        <h1>Mi día</h1>
      </header>

      <Link to="/sales/visit" className="sales-knock">
        <span className="sales-knock-icon" aria-hidden="true"><Icon name="door" size={26} /></span>
        <span><strong>Tocar una puerta</strong><small>Registra la visita, aunque no abran</small></span>
      </Link>

      {devueltos.length > 0 && (
        <section className="acta sales-block is-alert">
          <h2>Devueltos por Administración</h2>
          <p className="acta-lead">Corrígelos y vuelve a enviar.</p>
          <CaseList items={devueltos} />
        </section>
      )}

      <section className="acta sales-block">
        <div className="sales-block-head"><h2>Por terminar</h2><span className="billing-count">{prospectos.length}</span></div>
        {prospectos.length === 0 ? <p className="acta-empty">Nada pendiente. Las puertas que abran aparecen aquí hasta que las envíes.</p>
          : <CaseList items={prospectos} />}
        {enviados > 0 && <p className="acta-empty">{enviados} {enviados === 1 ? "expediente enviado" : "expedientes enviados"} esperando revisión · <Link to="/cases">ver todos</Link></p>}
      </section>

      <section className="acta sales-block">
        <h2>Mis programas y zonas</h2>
        {mios && mios.length === 0 && <p className="acta-empty">Todavía no tienes zona asignada. Pídesela a Administración; mientras tanto puedes registrar visitas y elegir el programa en el expediente.</p>}
        <ul className="sales-programs">
          {(mios ?? []).map((m) => (
            <li key={m.program.id}>
              <strong>{m.program.name}</strong>
              <span>{m.zones.map((z) => z.name).join(" · ")}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function CaseList({ items }: { items: { id: string; case_number: string; customer_name: string | null; address: string; program_name: string | null }[] }) {
  return (
    <ul className="sales-cases">
      {items.map((c) => (
        <li key={c.id}>
          <Link to={`/cases/${c.id}/form`}>
            {c.customer_name ? <Avatar name={c.customer_name} size="sm" /> : <span className="ui-avatar is-sm is-door" aria-hidden="true"><Icon name="door" size={16} /></span>}
            <span className="sales-case-text"><strong>{c.customer_name ?? c.address}</strong><small>{c.case_number}{c.program_name ? ` · ${c.program_name}` : " · sin programa"}</small></span>
            <span className="sales-case-go" aria-hidden="true"><Icon name="chevronRight" size={16} /></span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
