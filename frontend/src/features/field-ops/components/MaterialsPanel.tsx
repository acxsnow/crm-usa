import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  addMaterial,
  apiErrorMessage,
  deleteMaterial,
  fieldKeys,
  listMaterials,
  useRefreshProject,
} from "@/features/field-ops/module5Api";

/** Lo que la orden necesita (PDF §5.1). Lo arma Administración; el técnico lo ve. */
export function MaterialsPanel({ projectId, canManage, closed }: { projectId: string; canManage: boolean; closed: boolean }) {
  const { data: materiales } = useQuery({ queryKey: fieldKeys.materials(projectId), queryFn: () => listMaterials(projectId) });
  const refresh = useRefreshProject(projectId);
  const [descripcion, setDescripcion] = useState("");
  const [cantidad, setCantidad] = useState("1");
  const [unidad, setUnidad] = useState("");
  const [error, setError] = useState<string | null>(null);
  const editable = canManage && !closed;

  const add = useMutation({
    mutationFn: () => addMaterial(projectId, {
      description: descripcion, quantity: Number(cantidad), unit: unidad || null, sku: null, notes: null,
    }),
    onSuccess: () => {
      setError(null);
      setDescripcion("");
      setCantidad("1");
      setUnidad("");
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });
  const remove = useMutation({ mutationFn: deleteMaterial, onSuccess: refresh, onError: (err) => setError(apiErrorMessage(err)) });

  if (!editable && (materiales ?? []).length === 0) return null;
  return (
    <section className="panel">
      <div className="panel-heading">
        <h3>Materiales de la orden</h3>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <ul className="plain-list">
        {(materiales ?? []).map((m) => (
          <li key={m.id}>
            {m.quantity} {m.unit ?? ""} · {m.description}
            {editable && (
              <button type="button" className="link-button" onClick={() => remove.mutate(m.id)} disabled={remove.isPending}>
                Quitar
              </button>
            )}
          </li>
        ))}
      </ul>
      {editable && (
        <form className="inline-form" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <input aria-label="Descripción del material" placeholder="Línea de refrigerante 3/8 x 3/4" required
            value={descripcion} onChange={(e) => setDescripcion(e.target.value)} />
          <input aria-label="Cantidad" type="number" min={0.01} step={0.01} required style={{ width: "6rem" }}
            value={cantidad} onChange={(e) => setCantidad(e.target.value)} />
          <input aria-label="Unidad" placeholder="ft, und…" style={{ width: "6rem" }}
            value={unidad} onChange={(e) => setUnidad(e.target.value)} />
          <button type="submit" disabled={add.isPending}>Agregar</button>
        </form>
      )}
    </section>
  );
}
