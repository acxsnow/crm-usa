import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "../notifications/notifications.css";
import "../finance/finance.css";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { PaginationControls } from "@/components/PaginationControls";
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
        {lista.isLoading ? <p className="acta-empty">Cargando…</p> : lista.items.length === 0 ? (
          <p className="acta-empty">
            Todavía no hay listas. El cliente envía su listado por tipo de trabajo; mientras tanto se pueden armar aquí.
          </p>
        ) : (
          <div className="tablewrap"><table className="notices-table">
            <thead>
              <tr><th>Lista</th><th>Tipo de trabajo</th><th>Material</th><th>Estado</th><th /></tr>
            </thead>
            <tbody>
              {lista.items.map((k) => (
                <tr key={k.id}>
                  <td>
                    <strong>{k.name}</strong>
                    {k.description && <small>{k.description}</small>}
                  </td>
                  <td>{k.project_type ?? "—"}</td>
                  <td>
                    <details>
                      <summary>{k.items.length} renglones</summary>
                      <ul>
                        {k.items.map((r) => (
                          <li key={r.id}>
                            {r.section ? `${r.section} · ` : ""}
                            {r.item_name ?? "Artículo"}: {r.quantity} {r.unit_label ?? ""}
                            {r.spec_label ? ` (${r.spec_label})` : ""}
                            {r.is_required ? "" : " — opcional"}
                          </li>
                        ))}
                      </ul>
                    </details>
                  </td>
                  <td>{k.active ? "Activa" : "Inactiva"}</td>
                  <td className="is-action">
                    {puede && (
                      <>
                        <button type="button" className="acta-link" onClick={() => setEditando(k)}>Editar</button>
                        <button type="button" className="acta-link" disabled={borrar.isPending}
                          onClick={() => {
                            void confirmAction({ title: `¿Borrar «${k.name}»?`, message: "Las órdenes que ya la usaron no cambian.", confirmLabel: "Borrar", danger: true })
                              .then((ok) => { if (ok) borrar.mutate(k.id); });
                          }}>Borrar</button>
                      </>
                    )}
                  </td>
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

      <table className="materials-table">
        <thead>
          <tr>
            <th scope="col">Artículo</th><th scope="col">Cantidad</th><th scope="col">Medida / calibre</th>
            <th scope="col">Sección</th><th scope="col">Notas</th><th />
          </tr>
        </thead>
        <tbody>
          {renglones.map((r, i) => (
            <tr key={i}>
              <td>
                <ItemPicker label={`Artículo del renglón ${i + 1}`} itemId={r.item_id}
                  onChange={(a) => cambiar(i, { item_id: a?.id ?? "" })} />
              </td>
              <td>
                <input aria-label={`Cantidad del renglón ${i + 1}`} inputMode="decimal" value={r.quantity}
                  onChange={(e) => cambiar(i, { quantity: e.target.value })} />
              </td>
              <td>
                <input aria-label={`Medida del renglón ${i + 1}`} placeholder="1/4, 3/8, 12.000 BTU…"
                  value={r.spec_label ?? ""} onChange={(e) => cambiar(i, { spec_label: e.target.value })} />
              </td>
              <td>
                <input aria-label={`Sección del renglón ${i + 1}`} placeholder="Líneas, unidad exterior…"
                  value={r.section ?? ""} onChange={(e) => cambiar(i, { section: e.target.value })} />
              </td>
              <td>
                <input aria-label={`Notas del renglón ${i + 1}`} value={r.notes ?? ""}
                  onChange={(e) => cambiar(i, { notes: e.target.value })} />
              </td>
              <td>
                {renglones.length > 1 && (
                  <button type="button" className="acta-btn is-quiet"
                    onClick={() => setRenglones((a) => a.filter((_, j) => j !== i))}>Quitar</button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

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
