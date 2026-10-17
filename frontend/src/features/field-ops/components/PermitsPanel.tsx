import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import {
  apiErrorMessage,
  fieldKeys,
  listPermits,
  localISODate,
  recordPermit,
  updatePermit,
  useFieldCatalogs,
  useRefreshProject,
  type PermitInput,
} from "@/features/field-ops/module5Api";
import type { Permit, PermitStatus } from "@/types/fieldOps";

const hoy = () => localISODate();

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
    <div className="acta-body">
      {error && <p className="form-error" role="alert">{error}</p>}
      {permits && <SiguientePaso permits={permits} />}
      {permits && permits.length > 0 && (
        <div className="permit-list">
          {permits.map((p) => (
            <PermitCard key={p.id} permit={p} canManage={canManage} onError={setError} onChanged={refresh} />
          ))}
        </div>
      )}

      {canManage && <h4 className="permit-new-title">{permits?.length ? "Registrar otro permiso" : "Registrar el permiso"}</h4>}
      {canManage && (
        <form
          className="panel-form"
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
          <button type="submit" className="acta-btn is-primary" disabled={record.isPending}>
            {record.isPending ? "Guardando…" : "Registrar permiso"}
          </button>
        </form>
      )}
    </div>
  );
}

/** «15 oct 2026» a partir de una fecha ISO sin hora (sin correrse por la zona horaria). */
function fechaCorta(iso: string | null): string {
  if (!iso) return "";
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}

/** Qué falta, mirando todos los permisos del proyecto: una sola frase arriba de las tarjetas. */
function SiguientePaso({ permits }: { permits: Permit[] }) {
  if (permits.length === 0) {
    return <p className="permit-next">Registra el permiso que se radicó en la ciudad, o márcalo como «No requerido» con el motivo. Sin esto no se puede agendar la instalación.</p>;
  }
  if (permits.every((p) => p.is_cleared)) {
    return <p className="permit-next is-done">✓ Permisos listos. Ya se puede liberar la orden: elegir técnico y fecha de instalación.</p>;
  }
  return <p className="permit-next">Falta que la ciudad apruebe {permits.filter((p) => !p.is_cleared).length === 1 ? "el permiso" : "los permisos"} de abajo. Hasta entonces no se puede agendar la instalación.</p>;
}

/**
 * Un permiso como tarjeta con sus pasos (Radicado → Aprobado por la ciudad), una
 * frase con lo que falta y botones con la acción exacta. Antes era una fila de
 * tabla con dos fechas sin título y un botón «Aprobado» que no se entendía
 * (revisión manual del 16 de octubre).
 */
function PermitCard({ permit, canManage, onError, onChanged }: {
  permit: Permit; canManage: boolean; onError: (m: string) => void; onChanged: () => Promise<unknown>;
}) {
  const [accion, setAccion] = useState<"aprobar" | "rechazar" | null>(null);
  const [aprobadoEl, setAprobadoEl] = useState(hoy());
  const [venceEl, setVenceEl] = useState("");
  const [motivo, setMotivo] = useState("");
  const guardar = useMutation({
    mutationFn: (cambios: Partial<PermitInput>) => updatePermit(permit.id, cambios),
    onSuccess: async () => { setAccion(null); await onChanged(); },
    onError: (err) => onError(apiErrorMessage(err)),
  });

  const titulo = [permit.permit_type ? `Permiso ${permit.permit_type.toLowerCase()}` : "Permiso", permit.jurisdiction,
    permit.permit_number ? `N.º ${permit.permit_number}` : null].filter(Boolean).join(" · ");
  const radicado = permit.status !== "not_required";
  const aprobado = permit.status === "approved";

  let estado: { tono: "ok" | "wait" | "bad"; texto: string };
  if (permit.status === "not_required") estado = { tono: "ok", texto: `No requiere permiso: ${permit.not_required_reason ?? ""}` };
  else if (permit.status === "rejected") estado = { tono: "bad", texto: `La ciudad lo rechazó${permit.notes ? `: ${permit.notes}` : "."} Corrige lo que pidió y vuelve a radicarlo.` };
  else if (aprobado && permit.is_expired) estado = { tono: "bad", texto: `Venció el ${fechaCorta(permit.expires_on)}. Registra la renovación para poder instalar.` };
  else if (aprobado) estado = { tono: "ok", texto: permit.expires_on ? `Aprobado. Vale hasta el ${fechaCorta(permit.expires_on)}; te avisamos antes de que venza.` : "Aprobado. No tiene fecha de vencimiento registrada." };
  else estado = { tono: "wait", texto: "Falta que la ciudad lo apruebe. Cuando responda, regístralo aquí." };

  return (
    <article className={`permit-card is-${estado.tono}`}>
      <h4>{titulo}</h4>
      {radicado && (
        <ol className="permit-steps">
          <li className="is-done"><span aria-hidden="true">✓</span> Radicado<small>{permit.filed_on ? fechaCorta(permit.filed_on) : "sin fecha"}</small></li>
          <li className={aprobado ? "is-done" : permit.status === "rejected" ? "is-bad" : ""}>
            <span aria-hidden="true">{aprobado ? "✓" : permit.status === "rejected" ? "✕" : ""}</span> Aprobado por la ciudad
            <small>{aprobado ? fechaCorta(permit.approved_on) : permit.status === "rejected" ? "rechazado" : "pendiente"}</small>
          </li>
        </ol>
      )}
      <p className="permit-status" role="status">{estado.texto}</p>

      {canManage && accion === null && (
        <div className="permit-actions">
          {permit.status === "submitted" && (<>
            <button type="button" className="acta-btn is-primary" onClick={() => setAccion("aprobar")}>La ciudad lo aprobó</button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setAccion("rechazar")}>La ciudad lo rechazó</button>
          </>)}
          {aprobado && (
            <button type="button" className={`acta-btn ${permit.is_expired ? "is-primary" : "is-quiet"}`} onClick={() => {
              setAprobadoEl(hoy()); setVenceEl(permit.expires_on ?? ""); setAccion("aprobar");
            }}>{permit.is_expired ? "Registrar la renovación" : permit.expires_on ? "Cambiar fechas" : "Agregar fecha de vencimiento"}</button>
          )}
          {permit.status === "rejected" && (
            <button type="button" className="acta-btn is-primary" disabled={guardar.isPending}
              onClick={() => guardar.mutate({ status: "submitted", filed_on: hoy() })}>Volver a radicar (hoy)</button>
          )}
        </div>
      )}

      {accion === "aprobar" && (
        <form className="permit-form" onSubmit={(e) => {
          e.preventDefault();
          guardar.mutate({ status: "approved", approved_on: aprobadoEl, expires_on: venceEl || null });
        }}>
          <div className="field">
            <label htmlFor={`aprobado-${permit.id}`}>¿Qué día lo aprobó la ciudad?</label>
            <input id={`aprobado-${permit.id}`} type="date" required max={hoy()} value={aprobadoEl}
              onChange={(e) => setAprobadoEl(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor={`vence-${permit.id}`}>¿Hasta cuándo vale? <span className="optional">(opcional)</span></label>
            <input id={`vence-${permit.id}`} type="date" min={aprobadoEl || undefined} value={venceEl}
              onChange={(e) => setVenceEl(e.target.value)} />
            <small>Viene en el permiso. Con esta fecha te avisamos antes de que venza; vencido, no deja instalar.</small>
          </div>
          <div className="permit-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setAccion(null)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>
              {guardar.isPending ? "Guardando…" : "Guardar aprobación"}</button>
          </div>
        </form>
      )}

      {accion === "rechazar" && (
        <form className="permit-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate({ status: "rejected", notes: motivo.trim() }); }}>
          <div className="field">
            <label htmlFor={`motivo-${permit.id}`}>¿Por qué lo rechazó la ciudad?</label>
            <textarea id={`motivo-${permit.id}`} required minLength={3} rows={2} value={motivo}
              onChange={(e) => setMotivo(e.target.value)} />
            <small>Queda en el permiso para corregirlo antes de volver a radicar.</small>
          </div>
          <div className="permit-actions">
            <button type="button" className="acta-btn is-quiet" onClick={() => setAccion(null)}>Cancelar</button>
            <button type="submit" className="acta-btn is-primary" disabled={guardar.isPending}>
              {guardar.isPending ? "Guardando…" : "Guardar rechazo"}</button>
          </div>
        </form>
      )}
    </article>
  );
}

/** Los campos vacíos del formulario viajan como ausentes, no como "". */
function limpiar(input: PermitInput): PermitInput {
  return Object.fromEntries(Object.entries(input).filter(([, v]) => v !== "" && v != null)) as PermitInput;
}
