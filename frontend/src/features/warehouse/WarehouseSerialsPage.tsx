import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { serialKeys, warehouseCatalogs, warehouseKeys, type WarehouseSerial } from "./api";

const PAGE_SIZE = 25;

function dia(iso: string | null): string {
  return iso ? new Date(iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "";
}

/**
 * Dónde está cada equipo con serial (D-007): en bodega, entregado a una obra
 * con su orden de salida, o instalado. Se busca por el serial o por el nombre
 * del artículo; es la respuesta a «¿dónde quedó la unidad con este serial?».
 */
export function WarehouseSerialsPage() {
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const [filtros, setFiltros] = useState<Record<string, string>>({});

  const lista = usePaginatedQuery<WarehouseSerial>({
    key: serialKeys.all, path: "/warehouse/serials", pageSize: PAGE_SIZE,
    params: { q: filtros.q || undefined, status: filtros.status || undefined },
  });

  const campos: FilterFieldDef[] = [
    { key: "q", label: "Serial o artículo", type: "text", placeholder: "Ej. 2304A12345" },
    {
      key: "status", label: "Estado", type: "select",
      options: Object.entries(cat?.serial_statuses ?? {}).map(([value, label]) => ({ value, label })),
    },
  ];

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Seriales</h1>
          <p>
            Cada equipo con serial: si sigue en bodega, a qué obra salió y con qué orden, o si ya está instalado.
            El serial se anota al entregar la orden de salida.
          </p>
        </div>
      </header>

      <article className="acta">
        <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">
            {filtros.q || filtros.status ? "Ningún serial con este filtro." : "Todavía no hay seriales registrados."}
          </p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead>
              <tr><th>Serial</th><th>Artículo</th><th>Estado</th><th>Obra</th><th>Orden de salida</th></tr>
            </thead>
            <tbody>
              {lista.items.map((s) => (
                <tr key={s.id}>
                  <td className="mono"><strong>{s.serial}</strong></td>
                  <td>
                    {s.item_name ?? "Artículo"}
                    <small>{[s.brand, s.manufacturer_part, s.sku].filter(Boolean).join(" · ")}</small>
                  </td>
                  <td>
                    {s.status_label}
                    {s.status === "installed" && s.installed_at && <small>{dia(s.installed_at)}</small>}
                    {s.status === "delivered" && s.delivered_at && <small>{dia(s.delivered_at)}</small>}
                  </td>
                  <td>{s.project_title ?? "—"}</td>
                  <td>{s.release_number ?? "—"}</td>
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
