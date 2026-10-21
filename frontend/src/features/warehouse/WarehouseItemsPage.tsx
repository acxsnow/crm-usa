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
  saveItem,
  warehouseCatalogs,
  warehouseKeys,
  type WarehouseCatalogs,
  type WarehouseItem,
} from "./api";

const PAGE_SIZE = 25;

/**
 * Catálogo de la bodega: los materiales con su referencia, categoría, unidad y
 * mínimo. Es el dato que después usan las listas predefinidas y el presupuesto,
 * así que las categorías y las unidades salen del catálogo del backend y no se
 * escriben a mano.
 */
export function WarehouseItemsPage() {
  const { hasPermission } = useAuth();
  const puede = hasPermission("warehouse.manage");
  const { data: cat } = useQuery({ queryKey: warehouseKeys.catalogs, queryFn: warehouseCatalogs, staleTime: Infinity });
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [editando, setEditando] = useState<WarehouseItem | "new" | null>(null);

  const params = {
    q: filtros.q || undefined,
    category: filtros.category || undefined,
    active: filtros.active === "1" ? true : filtros.active === "0" ? false : undefined,
  };
  const lista = usePaginatedQuery<WarehouseItem>({
    key: warehouseKeys.items, path: "/warehouse/items", pageSize: PAGE_SIZE, params,
  });

  const campos: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, referencia o proveedor" },
    {
      key: "category", label: "Categoría", type: "select",
      options: Object.entries(cat?.categories ?? {}).map(([value, label]) => ({ value, label })),
    },
    {
      key: "active", label: "Estado", type: "select",
      options: [{ value: "1", label: "Activos" }, { value: "0", label: "Inactivos" }],
    },
  ];

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Artículos de bodega</h1>
          <p>El catálogo de materiales: referencia, categoría, unidad, costo y el mínimo desde el que hay que reponer.</p>
        </div>
        {puede && editando === null && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" onClick={() => setEditando("new")}>Nuevo artículo</button>
          </div>
        )}
      </header>

      {editando !== null && cat && (
        <ItemForm
          initial={editando === "new" ? null : editando}
          catalogs={cat}
          onClose={() => setEditando(null)}
        />
      )}

      <article className="acta">
        <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">Ningún artículo con este filtro.</p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead><tr><th>Artículo</th><th>Categoría</th><th>Unidad</th><th>Costo</th><th>Mínimo</th><th>Existencia</th><th /></tr></thead>
            <tbody>
              {lista.items.map((i) => (
                <tr key={i.id} className={i.active ? "" : "fin-inactive"}>
                  <td>
                    <strong>{i.name}</strong>
                    <small>{[i.sku ? `Ref. ${i.sku}` : null, i.supplier_name].filter(Boolean).join(" · ") || "—"}</small>
                    {i.has_serial && <small>Con serial</small>}
                  </td>
                  <td>{i.category_label}</td>
                  <td>{i.unit_label}</td>
                  <td className="mono">{money(i.unit_cost)}</td>
                  <td className="mono">{i.min_quantity ?? "—"}</td>
                  <td className="mono">{i.total_quantity}
                    {i.below_minimum && <span className="billing-chip is-rejected">Bajo mínimo</span>}</td>
                  <td>{puede && <button type="button" className="acta-link" onClick={() => setEditando(i)}>Editar</button>}</td>
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

function ItemForm({ initial, catalogs, onClose }: {
  initial: WarehouseItem | null;
  catalogs: WarehouseCatalogs;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const [item, setItem] = useState<Partial<WarehouseItem>>(initial ?? {
    name: "", sku: "", category: "other", unit: "unit", unit_cost: "0", supplier_name: "",
    has_serial: false, min_quantity: "", notes: "", active: true,
  });
  const [error, setError] = useState<string | null>(null);
  const guardar = useMutation({
    mutationFn: () => saveItem(initial?.id ?? null, {
      name: item.name ?? "",
      sku: item.sku || null,
      category: item.category || "other",
      unit: item.unit || "unit",
      unit_cost: item.unit_cost || "0",
      supplier_name: item.supplier_name || null,
      has_serial: !!item.has_serial,
      min_quantity: item.min_quantity || null,
      notes: item.notes || null,
      active: item.active ?? true,
    }),
    onSuccess: () => {
      setError(null);
      [warehouseKeys.items, warehouseKeys.stock, warehouseKeys.summary].forEach((key) =>
        qc.invalidateQueries({ queryKey: key }));
      onClose();
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  return (
    <form className="acta fin-form fin-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <h3 className="acta-section-title">{initial ? `Editar ${initial.name}` : "Nuevo artículo"}</h3>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="it-name">Nombre del material</label>
          <input id="it-name" value={item.name ?? ""} onChange={(e) => setItem({ ...item, name: e.target.value })} required />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="it-sku">Referencia / SKU</label>
          <input id="it-sku" value={item.sku ?? ""} onChange={(e) => setItem({ ...item, sku: e.target.value })} />
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="it-cat">Categoría</label>
          <select id="it-cat" value={item.category ?? "other"} onChange={(e) => setItem({ ...item, category: e.target.value })}>
            {Object.entries(catalogs.categories).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="it-unit">Unidad</label>
          <select id="it-unit" value={item.unit ?? "unit"} onChange={(e) => setItem({ ...item, unit: e.target.value })}>
            {Object.entries(catalogs.units).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
      </div>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="it-cost">Costo unitario (USD)</label>
          <input id="it-cost" inputMode="decimal" value={item.unit_cost ?? "0"} onChange={(e) => setItem({ ...item, unit_cost: e.target.value })} />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="it-min">Cantidad mínima (avisa al llegar aquí)</label>
          <input id="it-min" inputMode="decimal" placeholder="Vacío = sin aviso" value={item.min_quantity ?? ""} onChange={(e) => setItem({ ...item, min_quantity: e.target.value })} />
        </div>
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="it-sup">Proveedor habitual</label>
        <input id="it-sup" value={item.supplier_name ?? ""} onChange={(e) => setItem({ ...item, supplier_name: e.target.value })} />
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="it-notes">Notas</label>
        <textarea id="it-notes" rows={2} value={item.notes ?? ""} onChange={(e) => setItem({ ...item, notes: e.target.value })} />
      </div>
      <label className="billing-check">
        <input type="checkbox" checked={!!item.has_serial} onChange={(e) => setItem({ ...item, has_serial: e.target.checked })} />
        Lleva serial: cada unidad se rastrea por separado
      </label>
      <label className="billing-check">
        <input type="checkbox" checked={item.active ?? true} onChange={(e) => setItem({ ...item, active: e.target.checked })} />
        Activo (aparece en las existencias)
      </label>
      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || !item.name?.trim()}>
          {guardar.isPending ? "Guardando…" : "Guardar"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}
