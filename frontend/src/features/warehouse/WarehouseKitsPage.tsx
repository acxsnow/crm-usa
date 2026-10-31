import { Fragment, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, ExpandToggle, PaginatedTable, RowAction, RowActions } from "@/components/DataTable";
import { useAuth } from "@/features/auth/AuthContext";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { usePaginatedQuery } from "@/lib/usePaginatedQuery";
import { ItemPicker } from "./ItemPicker";
import {
  deleteKit,
  saveKit,
  warehouseKeys,
  type KitInput,
  type KitItemInput,
  type WarehouseKit,
} from "./api";
import { confirmAction } from "@/components/ui/ConfirmDialog";

const PAGE_SIZE = 25;

/**
 * Listas predefinidas por tipo de trabajo (punto 2 del cuestionario del 19 de
 * octubre).
 *
 * «Aires y pedestales siempre llevan el mismo material, a veces cambian algunas
 * cantidades o calibres». Aquí se arma esa lista base; el técnico la aplica al
 * pedir la salida y ajusta la copia, así que editar la lista no cambia nada de
 * lo que ya se pidió.
 */
export function WarehouseKitsPage() {
  const { hasPermission } = useAuth();
  const qc = useQueryClient();
  const puede = hasPermission("warehouse.kits_manage");
  const [filtros, setFiltros] = useState<Record<string, string>>({});
  const [editando, setEditando] = useState<WarehouseKit | "new" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const params = {
    q: filtros.q || undefined,
    active: filtros.active === "1" ? true : filtros.active === "0" ? false : undefined,
  };
  const lista = usePaginatedQuery<WarehouseKit>({
    key: warehouseKeys.kits, path: "/warehouse/kits", pageSize: PAGE_SIZE, params,
  });

  const borrar = useMutation({
    mutationFn: deleteKit,
    onSuccess: () => { setError(null); qc.invalidateQueries({ queryKey: warehouseKeys.kits }); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  const campos: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre de la lista" },
    {
      key: "active", label: "Estado", type: "select",
      options: [{ value: "1", label: "Activas" }, { value: "0", label: "Inactivas" }],
    },
  ];

  return (
    <div className="billing-page notices-page fin-page">
      <header className="billing-head">
        <div>
          <h1>Listas predefinidas</h1>
          <p>Lo que cada tipo de trabajo siempre lleva. El técnico aplica la lista al pedir la salida y ajusta cantidades y calibres en su orden.</p>
        </div>
        {puede && editando === null && (
          <div className="acta-actions">
            <button type="button" className="acta-btn is-primary" onClick={() => setEditando("new")}>Nueva lista</button>
          </div>
        )}
      </header>

      {editando !== null && (
        <KitForm
          key={editando === "new" ? "nueva" : editando.id}
          initial={editando === "new" ? null : editando}
          onClose={() => setEditando(null)}
        />
      )}

      {error && <p className="form-error" role="alert">{error}</p>}

      <article className="acta">
        <FilterBar fields={campos} values={filtros} onApply={setFiltros} onClear={() => setFiltros({})} />
        <PaginatedTable list={lista} getRowKey={(k) => k.id}
          emptyMessage="Todavía no hay listas. El cliente envía su listado por tipo de trabajo; mientras tanto se pueden armar aquí."
          expandable={{ render: (k) => <KitLines kit={k} /> }}
          columns={[
            { key: "lista", header: "Lista", render: (k) => (
              <>
                <strong>{k.name}</strong>
                {k.description && <small>{k.description}</small>}
              </>
            ) },
            { key: "tipo", header: "Tipo de trabajo", render: (k) => k.project_type ?? "—" },
            { key: "material", header: "Material", render: (k, fila) => (
              <ExpandToggle expanded={fila.expanded} onToggle={fila.toggle}>{k.items.length} renglones</ExpandToggle>
            ) },
            { key: "estado", header: "Estado", render: (k) => (k.active ? "Activa" : "Inactiva") },
            { key: "acciones", header: "", render: (k) => puede && (
              <RowActions>
                <RowAction onClick={() => setEditando(k)}>Editar</RowAction>
                <RowAction variant="danger" disabled={borrar.isPending} onClick={() => {
                  void confirmAction({ title: `¿Borrar «${k.name}»?`, message: "Las órdenes que ya la usaron no cambian.", confirmLabel: "Borrar", danger: true })
                    .then((ok) => { if (ok) borrar.mutate(k.id); });
                }}>Borrar</RowAction>
              </RowActions>
            ) },
          ]} />
      </article>
    </div>
  );
}

/**
 * Armar la lista: el nombre, para qué tipo de trabajo es y los renglones con su
 * cantidad y su calibre. La cantidad que se escribe aquí es la sugerida; cada
 * trabajo la ajusta después en su propia copia.
 */
function KitForm({ initial, onClose }: { initial: WarehouseKit | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [nombre, setNombre] = useState(initial?.name ?? "");
  const [tipo, setTipo] = useState(initial?.project_type ?? "");
  const [descripcion, setDescripcion] = useState(initial?.description ?? "");
  const [activa, setActiva] = useState(initial?.active ?? true);
  const [renglones, setRenglones] = useState<KitItemInput[]>(
    initial?.items.length
      ? initial.items.map((r) => ({
          item_id: r.item_id, quantity: r.quantity, spec_label: r.spec_label,
          section: r.section, is_required: r.is_required, notes: r.notes,
        }))
      : [{ item_id: "", quantity: "1", spec_label: "", section: "", notes: "" }],
  );
  const [error, setError] = useState<string | null>(null);

  const guardar = useMutation({
    mutationFn: () => {
      const body: KitInput = {
        name: nombre.trim(),
        project_type: tipo.trim() || null,
        description: descripcion.trim() || null,
        active: activa,
        items: renglones.filter((r) => r.item_id).map((r) => ({
          item_id: r.item_id, quantity: r.quantity,
          spec_label: r.spec_label?.trim() || null, section: r.section?.trim() || null,
          is_required: r.is_required !== false, notes: r.notes?.trim() || null,
        })),
      };
      return saveKit(initial?.id ?? null, body);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: warehouseKeys.kits }); onClose(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });

  function cambiar(i: number, campos: Partial<KitItemInput>) {
    setRenglones((actuales) => actuales.map((r, j) => (j === i ? { ...r, ...campos } : r)));
  }

  const conMaterial = renglones.filter((r) => r.item_id);

  return (
    <form className="acta fin-form fin-box" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <h3 className="acta-section-title">{initial ? `Editar «${initial.name}»` : "Nueva lista predefinida"}</h3>
      <p className="acta-lead">
        Las órdenes que ya usaron esta lista se quedan como están: al aplicarla, cada orden recibe su propia copia.
      </p>
      <div className="fin-row">
        <div className="form-field">
          <label className="form-label" htmlFor="kit-nombre">Nombre</label>
          <input id="kit-nombre" value={nombre} onChange={(e) => setNombre(e.target.value)} required maxLength={255}
            placeholder="Instalación de aire — estándar" />
        </div>
        <div className="form-field">
          <label className="form-label" htmlFor="kit-tipo">Tipo de trabajo</label>
          <input id="kit-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} maxLength={100}
            placeholder="hvac_install" />
        </div>
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor="kit-desc">Para qué sirve</label>
        <input id="kit-desc" value={descripcion} onChange={(e) => setDescripcion(e.target.value)} maxLength={500} />
      </div>

      <DataTable rows={renglones.map((r, i) => ({ ...r, i }))} isLoading={false} getRowKey={(r) => String(r.i)}
        columns={[
          { key: "articulo", header: "Artículo", render: (r) => (
            <ItemPicker label={`Artículo del renglón ${r.i + 1}`} itemId={r.item_id}
              onChange={(a) => cambiar(r.i, { item_id: a?.id ?? "" })} />
          ) },
          { key: "cantidad", header: "Cantidad", render: (r) => (
            <input aria-label={`Cantidad del renglón ${r.i + 1}`} inputMode="decimal" value={r.quantity}
              onChange={(e) => cambiar(r.i, { quantity: e.target.value })} />
          ) },
          { key: "medida", header: "Medida / calibre", render: (r) => (
            <input aria-label={`Medida del renglón ${r.i + 1}`} placeholder="1/4, 3/8, 12.000 BTU…"
              value={r.spec_label ?? ""} onChange={(e) => cambiar(r.i, { spec_label: e.target.value })} />
          ) },
          { key: "seccion", header: "Sección", render: (r) => (
            <input aria-label={`Sección del renglón ${r.i + 1}`} placeholder="Líneas, unidad exterior…"
              value={r.section ?? ""} onChange={(e) => cambiar(r.i, { section: e.target.value })} />
          ) },
          { key: "notas", header: "Notas", render: (r) => (
            <input aria-label={`Notas del renglón ${r.i + 1}`} value={r.notes ?? ""}
              onChange={(e) => cambiar(r.i, { notes: e.target.value })} />
          ) },
          { key: "acciones", header: "", render: (r) => renglones.length > 1 && (
            <RowActions>
              <RowAction variant="danger" onClick={() => setRenglones((a) => a.filter((_, j) => j !== r.i))}>Quitar</RowAction>
            </RowActions>
          ) },
        ]} />

      <div className="acta-actions">
        <button type="button" className="acta-btn is-quiet"
          onClick={() => setRenglones((a) => [...a, { item_id: "", quantity: "1", spec_label: "", section: "", notes: "" }])}>
          Agregar renglón
        </button>
        <label className="billing-check">
          <input type="checkbox" checked={activa} onChange={(e) => setActiva(e.target.checked)} /> Lista activa
        </label>
      </div>

      {error && <p className="form-error" role="alert">{error}</p>}
      <div className="acta-actions">
        <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending || !nombre.trim() || conMaterial.length === 0}>
          {guardar.isPending ? "Guardando…" : "Guardar la lista"}
        </button>
        <button type="button" className="acta-btn is-quiet" onClick={onClose}>Cancelar</button>
      </div>
    </form>
  );
}

/** Los renglones de una lista, por sección (mismo formato que los de una salida). */
function KitLines({ kit }: { kit: WarehouseKit }) {
  return (
    <div className="release-lines">
      <ul>
        {kit.items.map((r, i) => (
          <Fragment key={r.id}>
            {r.section && r.section !== (i > 0 ? kit.items[i - 1].section : null) && (
              <li className="release-lines-section">{r.section}</li>
            )}
            <li>
              <span className="release-line-text">
                <strong>{r.item_name ?? "Artículo"}</strong>{r.spec_label ? ` (${r.spec_label})` : ""}
                <span className="release-qty">
                  {Number(r.quantity).toLocaleString("es-CO", { maximumFractionDigits: 2 })} {r.unit_label ?? ""}
                </span>
                {r.is_required
                  ? <span className="billing-chip is-required">Obligatorio</span>
                  : <span className="billing-chip">Opcional</span>}
              </span>
            </li>
          </Fragment>
        ))}
      </ul>
    </div>
  );
}
