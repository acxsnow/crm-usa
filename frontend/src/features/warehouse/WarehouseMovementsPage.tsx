import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
import { money } from "@/features/finance/api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { warehouseCatalogs, warehouseKeys, type WarehouseMovement } from "./api";

const PAGE_SIZE = 25;

/**
 * El libro de movimientos de la bodega: de dónde salió y a dónde fue cada cosa.
 *
 * Es la trazabilidad que pide el cuestionario del 19 de octubre: cada entrega
 * queda con el número de la orden de salida como referencia, así que desde aquí
 * se ve quién sacó qué y para qué obra.
 */
export function WarehouseMovementsPage() {
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const [filtros, setFiltros] = useState<Record<string, string>>({});

  const params = {
    movement_type: filtros.movement_type || undefined,
    date_from: filtros.date_from || undefined,
    date_to: filtros.date_to || undefined,
  };
  const lista = usePaginatedQuery<WarehouseMovement>({
    key: warehouseKeys.movements, path: "/warehouse/movements", pageSize: PAGE_SIZE, params,
  });

  const campos: FilterFieldDef[] = [
    {
      key: "movement_type", label: "Tipo", type: "select",
      options: Object.entries(cat?.movement_types ?? {}).map(([value, label]) => ({ value, label })),
    },
    { key: "date_from", label: "Desde", type: "text", placeholder: "AAAA-MM-DD" },
    { key: "date_to", label: "Hasta", type: "text", placeholder: "AAAA-MM-DD" },
  ];

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Movimientos de bodega</h1>
          <p>Cada entrada, salida, traslado y ajuste, con la referencia de la orden que lo produjo y la obra a la que fue.</p>
        </div>
      </header>

      <article className="acta">
        <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">Ningún movimiento con este filtro.</p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead>
              <tr><th>Fecha</th><th>Artículo</th><th>Tipo</th><th>Cantidad</th><th>Dónde</th><th>Referencia</th><th>Valor</th></tr>
            </thead>
            <tbody>
              {lista.items.map((m) => (
                <tr key={m.id} className={m.movement_type === "salida" ? "fin-overdue" : ""}>
                  <td>{m.movement_date ?? "—"}</td>
                  <td>
                    <strong>{m.item_name ?? "Artículo"}</strong>
                    {m.note && <small>{m.note}</small>}
                  </td>
                  <td>{m.movement_type_label}</td>
                  <td className="mono">{m.quantity} <small>{m.unit_label ?? ""}</small></td>
                  <td>
                    {m.location_name ?? "—"}
                    {m.vendor_location_id && <small>Entra a la camioneta</small>}
                  </td>
                  <td>{m.reference ?? (m.project_id ? "Obra" : "—")}</td>
                  <td className="mono">{m.amount ? money(m.amount) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
        <PaginationControls {...lista.controls} />
      </article>
    </div>
  );
}
