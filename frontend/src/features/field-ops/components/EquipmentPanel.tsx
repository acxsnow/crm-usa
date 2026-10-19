import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { openActaStep } from "./InstallationRecord";

import {
  addEquipment,
  apiErrorMessage,
  confirmEquipment,
  deleteEquipment,
  fieldKeys,
  listEquipment,
  useFieldCatalogs,
  useRefreshProject,
  type EquipmentInput,
} from "@/features/field-ops/module5Api";

const VACIO: EquipmentInput = {
  equipment_type: "heat_pump_outdoor", brand: "", model: "", serial_number: "",
  quantity: 1, unit_label: "", notes: null,
};

/**
 * Equipos instalados como dato (spec D5.7): el cobro al programa necesita
 * marca, modelo y serial. El paso se completa con «Guardar equipos
 * instalados», no al agregar el primero; agregar o quitar uno pide guardar de
 * nuevo. Cerrar la instalación exige la lista guardada, y después quedan
 * congelados.
 */
export function EquipmentPanel({ projectId, canManage, closed, confirmedAt }: {
  projectId: string; canManage: boolean; closed: boolean; confirmedAt: string | null | undefined;
}) {
  const { data: catalogs } = useFieldCatalogs();
  const { data: equipos } = useQuery({ queryKey: fieldKeys.equipment(projectId), queryFn: () => listEquipment(projectId) });
  const refresh = useRefreshProject(projectId);
  const [form, setForm] = useState<EquipmentInput>(VACIO);
  const [error, setError] = useState<string | null>(null);
  const editable = canManage && !closed;

  const add = useMutation({
    mutationFn: () => addEquipment(projectId, { ...form, serial_number: form.serial_number || null, unit_label: form.unit_label || null }),
    onSuccess: () => {
      setError(null);
      setForm(VACIO);
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
    meta: { successMessage: "Equipo agregado. Cuando termines, guarda la lista." },
  });
  const remove = useMutation({
    mutationFn: deleteEquipment,
    onSuccess: refresh,
    onError: (err) => setError(apiErrorMessage(err)),
    meta: { successMessage: "Equipo quitado." },
  });
  const confirm = useMutation({
    mutationFn: () => confirmEquipment(projectId),
    onSuccess: async () => { setError(null); await refresh(); openActaStep("signatures"); },
    onError: (err) => setError(apiErrorMessage(err)),
    meta: { successMessage: "Equipos instalados guardados. Sigue con las firmas del acta." },
  });
  const hayEquipos = Boolean(equipos && equipos.length > 0);

  return (
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      {equipos && equipos.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr><th>Tipo</th><th>Marca y modelo</th><th>Serial</th><th>Cant.</th><th>Unidad</th>{editable && <th />}</tr>
            </thead>
            <tbody>
              {equipos.map((e) => (
                <tr key={e.id}>
                  <td>{catalogs?.equipment_types[e.equipment_type] ?? e.equipment_type}</td>
                  <td>{e.brand} {e.model}</td>
                  <td>{e.serial_number ?? "—"}</td>
                  <td>{e.quantity}</td>
                  <td>{e.unit_label ?? "—"}</td>
                  {editable && (
                    <td>
                      <button type="button" className="link-button" disabled={remove.isPending}
                        onClick={() => remove.mutate(e.id)}>Quitar</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="acta-empty">Sin equipos registrados.</p>
      )}

      {editable && hayEquipos && (
        confirmedAt ? (
          <p className="acta-hint">Lista guardada. Si agregas o quitas un equipo, tendrás que guardarla de nuevo.</p>
        ) : (
          <div className="equipment-save">
            <p className="acta-hint">Cuando termines de registrar todos los equipos de esta casa, guarda la lista para completar el paso.</p>
            <button type="button" className="acta-btn is-primary" disabled={confirm.isPending} onClick={() => confirm.mutate()}>
              {confirm.isPending ? "Guardando…" : "Guardar equipos instalados"}
            </button>
          </div>
        )
      )}

      {editable && (
        <form className="panel-form" onSubmit={(e) => { e.preventDefault(); add.mutate(); }}>
          <div className="field">
            <label htmlFor="equipment-type">Tipo</label>
            <select id="equipment-type" value={form.equipment_type}
              onChange={(e) => setForm({ ...form, equipment_type: e.target.value })}>
              {Object.entries(catalogs?.equipment_types ?? {}).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="equipment-brand">Marca</label>
            <input id="equipment-brand" required value={form.brand} onChange={(e) => setForm({ ...form, brand: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="equipment-model">Modelo</label>
            <input id="equipment-model" required value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="equipment-serial">Serial</label>
            <input id="equipment-serial" value={form.serial_number ?? ""} onChange={(e) => setForm({ ...form, serial_number: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="equipment-qty">Cantidad</label>
            <input id="equipment-qty" type="number" min={1} max={50} value={form.quantity}
              onChange={(e) => setForm({ ...form, quantity: Number(e.target.value) })} />
          </div>
          <div className="field">
            <label htmlFor="equipment-unit">Unidad o espacio</label>
            <input id="equipment-unit" placeholder="Casa principal, Spc 14…" value={form.unit_label ?? ""}
              onChange={(e) => setForm({ ...form, unit_label: e.target.value })} />
          </div>
          <button type="submit" className={`acta-btn${hayEquipos ? "" : " is-primary"}`} disabled={add.isPending}>
            {add.isPending ? "Guardando…" : "Agregar equipo"}
          </button>
        </form>
      )}
    </div>
  );
}
