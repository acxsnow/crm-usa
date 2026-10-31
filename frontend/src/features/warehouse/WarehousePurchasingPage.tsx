import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { PaginatedTable } from "@/components/DataTable";
import { useClientPagination } from "@/lib/useClientPagination";
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
  // Es un reporte calculado completo: se pagina aquí y los totales suman todo.
  const lista = useClientPagination(data?.rows, isLoading);

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Compras sugeridas</h1>
          <p>
            Lo que a las obras en curso les falta por entregar de su presupuesto, menos lo que hay en bodega.
            Lo que ya salió para una obra no se vuelve a comprar, y lo que sobra tampoco.
          </p>
        </div>
      </header>

      <article className="acta">
        <PaginatedTable list={lista} getRowKey={(f) => f.item_id}
          emptyMessage="No hay nada que comprar todavía: hace falta un presupuesto aprobado en una obra en curso."
          columns={[
            { key: "articulo", header: "Artículo", render: (f) => <><strong>{f.item_name}</strong>{f.sku && <small>{f.sku}</small>}</> },
            { key: "presupuestado", header: "Presupuestado", render: (f) => `${f.budgeted} ${f.unit}` },
            { key: "entregado", header: "Ya entregado", render: (f) => `${f.delivered} ${f.unit}` },
            { key: "falta", header: "Falta entregar", render: (f) => `${f.pending} ${f.unit}` },
            { key: "bodega", header: "En bodega", render: (f) => `${f.in_stock} ${f.unit}` },
            { key: "comprar", header: "Por comprar", render: (f) => <strong>{f.to_buy} {f.unit}</strong> },
            { key: "unitario", header: "Costo unitario", className: "mono", render: (f) => dinero(f.unit_cost) },
            { key: "estimado", header: "Costo estimado", className: "mono", render: (f) => dinero(f.estimated_cost) },
            { key: "existencia", header: "Existencia", render: (f) => (f.below_minimum ? "En o bajo el mínimo" : "Suficiente") },
          ]}
          footer={["Total", data?.totals.budgeted, null, null, null, data?.totals.to_buy, null, null, `${data?.totals.items ?? 0} artículos`]} />
      </article>
    </div>
  );
}
