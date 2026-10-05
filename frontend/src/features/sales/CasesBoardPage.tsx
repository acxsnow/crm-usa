import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "./sales.css";
import { useAuth } from "@/features/auth/AuthContext";
import { getBoard, salesKeys } from "./api";

const SUB: Record<string, string> = {
  returned: "Devuelto", pending_review: "En revisión", ready_to_submit: "Listo para el programa",
  submitted_to_program: "En el programa", program_review: "Revisión del programa",
};

/**
 * Expedientes por etapa (kanban, módulo 2). Reemplaza la pantalla del modelo
 * anterior. Los cierres tempranos (no abrió, no le interesa, no califica) no
 * se muestran salvo que se pidan. El vendedor ve los suyos; Administración y
 * Gerencia, todos.
 */
export function CasesBoardPage() {
  const { hasPermission } = useAuth();
  const [tempranos, setTempranos] = useState(false);
  // Administración abre la revisión; el vendedor, su formulario.
  const revisa = hasPermission("cases.review") || hasPermission("cases.approve");
  const { data, isLoading } = useQuery({ queryKey: salesKeys.board(tempranos), queryFn: () => getBoard(tempranos) });
  const columnas = (data ?? []).filter((c) => c.count > 0 || ["new_prospect", "pending_approval", "approved"].includes(c.code));
  return (
    <div className="billing-page board-page">
      <header className="billing-head board-head">
        <div>
          <h1>Expedientes</h1>
          <p>Cada puerta con su etapa. {hasPermission("cases.read_all") ? "Todos los vendedores." : "Los tuyos."}</p>
        </div>
        <div className="acta-actions">
          <label className="billing-check"><input type="checkbox" checked={tempranos} onChange={(e) => setTempranos(e.target.checked)} /> Mostrar puertas cerradas</label>
          {hasPermission("cases.create") && <Link to="/sales/visit" className="acta-btn is-primary">Tocar puerta</Link>}
        </div>
      </header>
      {isLoading ? <p className="acta-empty">Cargando…</p> : (
        <div className="board">
          {columnas.map((col) => (
            <section key={col.code} className="board-col" aria-label={col.label}>
              <h2><span>{col.label}</span><span className="billing-count">{col.count}</span></h2>
              {col.cases.length === 0 && <p className="acta-empty">Vacío</p>}
              <ul>
                {col.cases.map((c) => (
                  <li key={c.id}>
                    <Link to={revisa && col.code !== "new_prospect" ? `/cases/${c.id}/review` : `/cases/${c.id}/form`} className="board-card">
                      <strong>{c.customer_name ?? c.address ?? c.case_number}</strong>
                      <small>{c.case_number}{c.program_name ? ` · ${c.program_name}` : ""}</small>
                      {c.customer_name && <small>{c.address}</small>}
                      {c.substatus_code && SUB[c.substatus_code] && (
                        <span className={`billing-chip ${c.substatus_code === "returned" ? "is-rejected" : "is-submitted"}`}>{SUB[c.substatus_code]}</span>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
              {col.count > col.cases.length && <p className="acta-empty">y {col.count - col.cases.length} más</p>}
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
