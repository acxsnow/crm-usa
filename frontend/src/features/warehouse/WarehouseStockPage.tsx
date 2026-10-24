import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { money } from "@/features/finance/api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import {
  importCatalog,
  stockSummary,
  warehouseCatalogs,
  warehouseKeys,
  type ImportResult,
  type WarehouseItem,
} from "./api";

const PAGE_SIZE = 25;

/**
 * Existencias de la bodega (Fase 0 del plan control-bodega).
 *
 * Es la pantalla del conteo del fin de semana: qué hay hoy, dónde está (bodega
 * o camioneta) y qué está en o por debajo del mínimo. Aquí no se mueve nada a
 * mano: la existencia cambia por la carga del Excel, los conteos y —cuando
 * exista— las órdenes de salida autorizadas.
 */
export function WarehouseStockPage() {
  const { hasPermission } = useAuth();
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [importar, setImportar] = useState(false);

  const params = {
    q: filtros.q || undefined,
    category: filtros.category || undefined,
    low_only: filtros.low_only ? true : undefined,
  };
  const lista = usePaginatedQuery<WarehouseItem>({
    key: warehouseKeys.stock, path: "/warehouse/stock", pageSize: PAGE_SIZE, params,
  });
  const { data: resumen } = useQuery({ queryKey: warehouseKeys.summary, queryFn: stockSummary });

  const campos: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, referencia o proveedor" },
    {
      key: "category", label: "Categoría", type: "select",
      options: Object.entries(cat?.categories ?? {}).map(([value, label]) => ({ value, label })),
    },
    { key: "low_only", label: "Existencia", type: "select", options: [{ value: "1", label: "En o bajo el mínimo" }] },
  ];

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Existencias de bodega</h1>
          <p>Qué hay hoy en la bodega y en las camionetas. El saldo solo lo mueven las entradas, las salidas autorizadas y los conteos.</p>
        </div>
        {hasPermission("warehouse.manage") && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" onClick={() => setImportar((v) => !v)}>
              {importar ? "Cerrar" : "Importar catálogo"}
            </button>
          </div>
        )}
      </header>

      {importar && <ImportCatalog onClose={() => setImportar(false)} />}

      <div className="fin-kpis">
        <div className="fin-kpi"><small>Artículos activos</small><strong>{lista.total}</strong></div>
        <div className={`fin-kpi${(resumen?.low_count ?? 0) > 0 ? " is-alert" : ""}`}>
          <small>En o bajo el mínimo</small><strong>{resumen?.low_count ?? 0}</strong>
        </div>
      </div>

      <article className="acta">
        <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">Ningún artículo con este filtro. Carga el catálogo del Excel para empezar.</p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead><tr><th>Artículo</th><th>Categoría</th><th>Existencia</th><th>Mínimo</th><th>Dónde</th><th>Valor</th></tr></thead>
            <tbody>
              {lista.items.map((i) => (
                <tr key={i.id} className={i.below_minimum ? "fin-overdue" : ""}>
                  <td>
                    <strong>{i.name}</strong>
                    <small>{[i.sku ? `Ref. ${i.sku}` : null, i.supplier_name].filter(Boolean).join(" · ") || "—"}</small>
                    {i.has_serial && <small>Con serial: se rastrea por equipo</small>}
                  </td>
                  <td>{i.category_label}</td>
                  <td className="mono">
                    {i.total_quantity} <small>{i.unit_label}</small>
                    {i.below_minimum && <span className="billing-chip is-rejected">Bajo mínimo</span>}
                  </td>
                  <td className="mono">{i.min_quantity ?? "—"}</td>
                  <td>
                    {i.by_location.length === 0 ? "—" : i.by_location.map((l) => (
                      <small key={l.location_id}>{l.name}: {l.quantity}</small>
                    ))}
                  </td>
                  <td className="mono">{money(i.value)}</td>
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

/**
 * Carga del Excel del cliente. El mismo archivo se sube el fin de semana del
 * conteo: los artículos nuevos entran con su cantidad como conteo inicial y a
 * los que ya existen se les actualizan los datos por su referencia (SKU).
 */
function ImportCatalog({ onClose }: { onClose: () => void }) {
  const qc = useQueryClient();
  const [archivo, setArchivo] = useState<File | null>(null);
  const [reemplazar, setReemplazar] = useState(false);
  const [resultado, setResultado] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const subir = useMutation({
    mutationFn: () => importCatalog(archivo as File, reemplazar),
    onSuccess: (r) => {
      setError(null);
      setResultado(r);
      [warehouseKeys.stock, warehouseKeys.items, warehouseKeys.summary, warehouseKeys.catalogs, warehouseKeys.categories].forEach((key) =>
        qc.invalidateQueries({ queryKey: key }));
    },
    onError: (e) => { setResultado(null); setError(apiErrorMessage(e)); },
  });
  return (
    <article className="acta fin-form fin-box">
      <h3 className="acta-section-title">Importar catálogo del Excel</h3>
      <p className="acta-lead">Sube el archivo con la hoja «Catálogo». Los artículos nuevos entran con la cantidad del archivo como conteo inicial; los que ya existen se reconocen por su referencia (SKU) y solo se actualizan sus datos.</p>
      <div className="form-field">
        <label className="form-label" htmlFor="wh-file">Archivo del catálogo (.xlsx)</label>
        <input id="wh-file" type="file" accept=".xlsx" onChange={(e) => setArchivo(e.target.files?.[0] ?? null)} />
      </div>
      <label className="billing-check">
        <input type="checkbox" checked={reemplazar} onChange={(e) => setReemplazar(e.target.checked)} />
        Corregir la existencia con la cantidad del archivo (deja un ajuste en el libro de movimientos)
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      {resultado && (
        <div className="info-banner" role="status">
          Hoja «{resultado.sheet}»: {resultado.rows_read} filas leídas. {resultado.creados} artículos nuevos, {resultado.actualizados} actualizados, {resultado.conteo_inicial} con conteo inicial.
          {resultado.categorias_nuevas?.length > 0 && (
            <p>Categorías nuevas que traía el archivo: {resultado.categorias_nuevas.join(", ")}. Se pueden renombrar o desactivar en Artículos › Categorías.</p>
          )}
          {resultado.errores.length > 0 && (
            <ul>{resultado.errores.slice(0, 10).map((e) => <li key={e.fila}>Fila {e.fila}: {e.error}</li>)}</ul>
          )}
          {resultado.errores.length > 10 && <p>…y {resultado.errores.length - 10} filas más con aviso.</p>}
        </div>
      )}
      <div className="acta-actions">
        <button type="button" className="acta-btn is-primary" disabled={!archivo || subir.isPending} onClick={() => subir.mutate()}>
          {subir.isPending ? "Cargando…" : "Cargar archivo"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cerrar</button>
      </div>
    </article>
  );
}
