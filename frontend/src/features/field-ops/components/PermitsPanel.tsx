import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiErrorMessage,
  fieldKeys,
  listPermits,
  recordPermit,
  updatePermit,
  useFieldCatalogs,
  useRefreshProject,
  type PermitInput,
} from "@/features/field-ops/module5Api";
import type { Permit, PermitStatus } from "@/types/fieldOps";

const hoy = () => new Date().toISOString().slice(0, 10);

/**
 * Permisos municipales (spec D5.5). Registrar el primero pasa el expediente a
 * «Permiso en trámite»; cuando todos quedan despejados, a «Listo para
 * instalar». Vencido no es un estado: lo calcula el backend.
 */
export function PermitsPanel({ projectId, canManage }: { projectId: string; canManage: boolean }) {
  const { data: catalogs } = useFieldCatalogs();
  const { data: permits } = useQuery({ queryKey: fieldKeys.permits(projectId), queryFn: () => listPermits(projectId) });
  const refresh = useRefreshProject(projectId);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<PermitInput>({ jurisdiction: "", status: "submitted", filed_on: hoy() });
  const record = useMutation({
    mutationFn: () => recordPermit(projectId, limpiar(form)),
    onSuccess: () => {
      setError(null);
      setForm({ jurisdiction: "", status: "submitted", filed_on: hoy() });
      return refresh();
    },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  return (
    <section className="panel">
      <div className="panel-heading">
        <h3>Permisos municipales</h3>
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      {permits && permits.length > 0 ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Ciudad o condado</th>
                <th>Número</th>
                <th>Estado</th>
                <th>Aprobado</th>
                <th>Vence</th>
                {canManage && <th />}
              </tr>
            </thead>
            <tbody>
              {permits.map((p) => (
                <PermitRow key={p.id} permit={p} statusLabel={catalogs?.permit_statuses[p.status] ?? p.status}
                  canManage={canManage} onError={setError} onChanged={refresh} />
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="empty-state">Sin permisos registrados.</p>
      )}

      {canManage && (
        <form
          className="compact-form"
          onSubmit={(e) => {
            e.preventDefault();
            record.mutate();
          }}
        >
          <div className="field">
            <label htmlFor="permit-jurisdiction">Ciudad o condado</label>
            <input id="permit-jurisdiction" required value={form.jurisdiction ?? ""}
              onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="permit-number">Número</label>
            <input id="permit-number" value={form.permit_number ?? ""}
              onChange={(e) => setForm({ ...form, permit_number: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="permit-type">Tipo</label>
            <input id="permit-type" placeholder="Mecánico, eléctrico…" value={form.permit_type ?? ""}
              onChange={(e) => setForm({ ...form, permit_type: e.target.value })} />
          </div>
          <div className="field">
            <label htmlFor="permit-status">Estado</label>
            <select id="permit-status" value={form.status}
              onChange={(e) => setForm({ ...form, status: e.target.value as PermitStatus })}>
              {Object.entries(catalogs?.permit_statuses ?? {}).map(([code, label]) => (
                <option key={code} value={code}>{label}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="permit-filed">Radicado el</label>
            <input id="permit-filed" type="date" max={hoy()} value={form.filed_on ?? ""}
              onChange={(e) => setForm({ ...form, filed_on: e.target.value })} />
          </div>
          {form.status === "approved" && (
            <>
              <div className="field">
                <label htmlFor="permit-approved">Aprobado el</label>
                <input id="permit-approved" type="date" required value={form.approved_on ?? ""}
                  onChange={(e) => setForm({ ...form, approved_on: e.target.value })} />
              </div>
              <div className="field">
                <label htmlFor="permit-expires">Vence el</label>
                <input id="permit-expires" type="date" value={form.expires_on ?? ""}
                  onChange={(e) => setForm({ ...form, expires_on: e.target.value })} />
              </div>
            </>
          )}
          {form.status === "not_required" && (
            <div className="field">
              <label htmlFor="permit-reason">Por qué no se requiere</label>
              <input id="permit-reason" required value={form.not_required_reason ?? ""}
                onChange={(e) => setForm({ ...form, not_required_reason: e.target.value })} />
            </div>
          )}
          <button type="submit" className="primary-button" disabled={record.isPending}>
            {record.isPending ? "Guardando…" : "Registrar permiso"}
          </button>
        </form>
      )}
    </section>
  );
}

function PermitRow({ permit, statusLabel, canManage, onError, onChanged }: {
  permit: Permit; statusLabel: string; canManage: boolean;
  onError: (m: string) => void; onChanged: () => Promise<unknown>;
}) {
  const [aprobadoEl, setAprobadoEl] = useState(hoy());
  const [venceEl, setVenceEl] = useState("");
  const approve = useMutation({
    mutationFn: () => updatePermit(permit.id, { status: "approved", approved_on: aprobadoEl, expires_on: venceEl || null }),
    onSuccess: onChanged,
    onError: (err) => onError(apiErrorMessage(err)),
  });
  const pendiente = permit.status === "submitted";

  return (
    <tr>
      <td>{permit.jurisdiction}{permit.permit_type ? ` · ${permit.permit_type}` : ""}</td>
      <td>{permit.permit_number ?? "—"}</td>
      <td>
        <span className={`status-pill ${permit.is_cleared ? "status-completed" : "status-pending"}`}>{statusLabel}</span>
        {permit.is_expired && <span className="status-pill status-overdue">Vencido</span>}
        {permit.not_required_reason && <small> {permit.not_required_reason}</small>}
      </td>
      <td>{permit.approved_on ?? "—"}</td>
      <td>{permit.expires_on ?? "—"}</td>
      {canManage && (
        <td>
          {pendiente && (
            <form className="inline-form" onSubmit={(e) => { e.preventDefault(); approve.mutate(); }}>
              <input type="date" aria-label="Fecha de aprobación" required value={aprobadoEl}
                onChange={(e) => setAprobadoEl(e.target.value)} />
              <input type="date" aria-label="Fecha de vencimiento" value={venceEl}
                onChange={(e) => setVenceEl(e.target.value)} />
              <button type="submit" disabled={approve.isPending}>Aprobado</button>
            </form>
          )}
        </td>
      )}
    </tr>
  );
}

/** Los campos vacíos del formulario viajan como ausentes, no como "". */
function limpiar(input: PermitInput): PermitInput {
  return Object.fromEntries(Object.entries(input).filter(([, v]) => v !== "" && v != null)) as PermitInput;
}
