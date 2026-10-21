import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { getPurchasing, warehouseKeys } from "./api";

const MONEDA = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

function dinero(valor: string | null | undefined): string {
  if (valor === null || valor === undefined) return "—";
  return MONEDA.format(Number(valor));
}

/**
 * Compras por adelantado (punto 3 del cuestionario del 19 de octubre).
 *
 * «El inventario lo hacen el fin de semana»: con el presupuesto de las obras que
 * todavía no terminan se sabe qué material va a hacer falta y cuánto hay en
 * bodega, así que la compra del fin de semana sale de aquí y no de la memoria.
 */
export function WarehousePurchasingPage() {
  const { data, isLoading } = useQuery({ queryKey: warehouseKeys.purchasing, queryFn: getPurchasing });

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Compras sugeridas</h1>
          <p>
            Lo que las obras en curso ya presupuestaron, menos lo que hay en bodega. Lo que sobra no se
            compra: la columna de la derecha es solo lo que falta.
          </p>
        </div>
      </header>

      <article className="acta">
        {isLoading ? <p className="acta-empty">Cargando…</p> : (data?.rows.length ?? 0) === 0 ? (
          <p className="acta-empty">
            No hay nada que comprar todavía: hace falta un presupuesto aprobado en una obra en curso.
          </p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead>
              <tr>
                <th>Artículo</th><th>Presupuestado</th><th>En bodega</th><th>Por comprar</th>
                <th>Costo unitario</th><th>Costo estimado</th><th>Existencia</th>
              </tr>
            </thead>
            <tbody>
              {(data?.rows ?? []).map((f) => (
                <tr key={f.item_id}>
                  <td>
                    <strong>{f.item_name}</strong>
                    {f.sku && <small>{f.sku}</small>}
                  </td>
                  <td>{f.budgeted} {f.unit}</td>
                  <td>{f.in_stock} {f.unit}</td>
                  <td><strong>{f.to_buy} {f.unit}</strong></td>
                  <td>{dinero(f.unit_cost)}</td>
                  <td>{dinero(f.estimated_cost)}</td>
                  <td>{f.below_minimum ? "En o bajo el mínimo" : "Suficiente"}</td>
                </tr>
              ))}
              <tr>
                <td><strong>Total</strong></td>
                <td><strong>{data?.totals.budgeted}</strong></td>
                <td />
                <td><strong>{data?.totals.to_buy}</strong></td>
                <td colSpan={3}><strong>{data?.totals.items} artículos</strong></td>
              </tr>
            </tbody>
          </table></div>
        )}
      </article>
    </div>
  );
}
