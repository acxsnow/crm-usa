import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  apiErrorMessage,
  authorizeExtraVisit,
  cancelProject,
  getCancellationCheck,
  getFieldOpsSettings,
  getVisitStatus,
  listFailedVisits,
  recordFailedVisit,
  saveFieldOpsSettings,
  useFieldCatalogs,
  useRefreshProject,
  visitKeys,
} from "@/features/field-ops/module5Api";
import type { Project } from "@/types/fieldOps";

const fechaCorta = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { day: "numeric", month: "short" });

/**
 * Visitas fallidas y límite de reagendamiento (D-001), dentro de «Orden liberada».
 *
 * - El técnico responsable (o la oficina) marca que la visita no se pudo hacer:
 *   motivo, qué pasó y el GPS. La obra queda sin fecha para agendarla otra vez.
 * - Al llegar al límite de la organización ya no se agenda: quien despacha
 *   autoriza otro intento con su motivo, o se cancela la obra.
 */
export function FailedVisitsStep({ project, canReport, canSchedule, coords }: {
  project: Project;
  canReport: boolean;
  canSchedule: boolean;
  coords: { latitude: number; longitude: number } | null;
}) {
  const refresh = useRefreshProject(project.id);
  const { data: catalogos } = useFieldCatalogs();
  const motivos = catalogos?.visit_failure_reasons ?? {};
  const { data: estado } = useQuery({ queryKey: visitKeys.status(project.id), queryFn: () => getVisitStatus(project.id) });
  const { data: historial } = useQuery({
    queryKey: visitKeys.list(project.id), queryFn: () => listFailedVisits(project.id),
    enabled: (project.failed_visits_count ?? 0) > 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [nota, setNota] = useState("");
  const [motivoExtra, setMotivoExtra] = useState("");
  const abierta = project.status !== "completed" && project.status !== "cancelled";

  const fallida = useMutation({
    mutationFn: () => recordFailedVisit(project.id, {
      reason_code: motivo, notes: nota, latitude: coords?.latitude, longitude: coords?.longitude,
    }),
    onSuccess: () => { setError(null); setAbierto(false); setMotivo(""); setNota(""); return refresh(); },
    onError: (err) => setError(apiErrorMessage(err)),
  });
  const extra = useMutation({
    mutationFn: () => authorizeExtraVisit(project.id, motivoExtra),
    onSuccess: () => { setError(null); setMotivoExtra(""); return refresh(); },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  const intentos = estado?.failed_visits ?? project.failed_visits_count ?? 0;
  if (!abierta && intentos === 0) return null;
  return (
    <div className="visits-step">
      {error && <p className="form-error" role="alert">{error}</p>}
      {estado && intentos > 0 && (estado.limit_reached || !(historial ?? []).length) && (
        <p className={`acta-lead${estado.limit_reached ? " is-warning" : ""}`}>
          {intentos} de {estado.limit} permitidas
          {estado.extra_visits_authorized > 0 && ` (incluye ${estado.extra_visits_authorized} autorizada${estado.extra_visits_authorized > 1 ? "s" : ""} de más)`}.
          {estado.limit_reached && abierta && " Llegó al límite: para agendarla otra vez hay que autorizar otro intento o cancelar la obra."}
        </p>
      )}

      {abierta && estado?.limit_reached && canSchedule && (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); extra.mutate(); }}>
          <label htmlFor="visita-extra">Por qué se autoriza otro intento</label>
          <input id="visita-extra" required minLength={5} value={motivoExtra}
            onChange={(e) => setMotivoExtra(e.target.value)} placeholder="El cliente llamó y confirmó que estará el jueves" />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={extra.isPending}>
              {extra.isPending ? "Autorizando…" : "Autorizar otro intento"}
            </button>
          </div>
        </form>
      )}

      {abierta && canReport && project.scheduled_date && (
        !abierto ? (
          <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
            <button type="button" className="acta-btn is-small" onClick={() => setAbierto(true)}>
              No se pudo hacer la visita
            </button>
          </div>
        ) : (
          <form className="panel-form" onSubmit={(e) => { e.preventDefault(); fallida.mutate(); }}>
            <p className="acta-lead" style={{ gridColumn: "1 / -1" }}>
              La visita del {fechaCorta(project.scheduled_date)} queda como fallida y la obra vuelve a por agendar.
              El material se queda en la camioneta hasta que Administración decida.
            </p>
            <div className="field">
              <label htmlFor="visita-motivo">Qué pasó</label>
              <select id="visita-motivo" required value={motivo} onChange={(e) => setMotivo(e.target.value)}>
                <option value="">Elige el motivo</option>
                {Object.entries(motivos).map(([codigo, etiqueta]) => (
                  <option key={codigo} value={codigo}>{etiqueta}</option>
                ))}
              </select>
            </div>
            <div className="field" style={{ gridColumn: "1 / -1" }}>
              <label htmlFor="visita-nota">Cuéntalo</label>
              <textarea id="visita-nota" required minLength={5} rows={3} value={nota}
                onChange={(e) => setNota(e.target.value)}
                placeholder="Toqué tres veces, llamé al cliente y no contestó. El vecino dice que salió de viaje." />
            </div>
            <p className="acta-lead" style={{ gridColumn: "1 / -1" }}>
              {coords ? "Se guarda con tu ubicación actual." : "Sin GPS: se guarda sin ubicación."}
            </p>
            <div className="acta-actions" style={{ gridColumn: "1 / -1" }}>
              <button type="submit" className="acta-btn is-primary" disabled={fallida.isPending}>
                {fallida.isPending ? "Guardando…" : "Registrar visita fallida"}
              </button>
              <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Cancelar</button>
            </div>
          </form>
        )
      )}

      {(historial ?? []).length > 0 && (
        <div className="visit-history">
          <h5>Visitas fallidas{estado ? ` · ${intentos} de ${estado.limit}` : ""}</h5>
          <ul>
            {(historial ?? []).map((v) => (
              <li key={v.id}>
                <div className="visit-history-head">
                  <strong>{v.reason_label}</strong>
                  <span>
                    {v.scheduled_date ? fechaCorta(v.scheduled_date) : "Sin fecha"}
                    {v.recorded_by_name ? ` · ${v.recorded_by_name}` : ""}
                    {v.latitude != null && v.longitude != null ? " · con GPS" : " · sin GPS"}
                  </span>
                </div>
                <p>{v.notes}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

/**
 * Cancelar la obra (D-001): con motivo; las salidas sin entregar se anulan con la obra y el
 * material entregado reintegrado o explicado. Solo `projects.close`.
 */
export function CancelProjectStep({ project, canCancel }: { project: Project; canCancel: boolean }) {
  const refresh = useRefreshProject(project.id);
  const [abierto, setAbierto] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [notaMaterial, setNotaMaterial] = useState("");
  const [hableConTecnico, setHableConTecnico] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: chequeo } = useQuery({
    queryKey: visitKeys.cancellation(project.id),
    queryFn: () => getCancellationCheck(project.id),
    enabled: abierto,
  });
  const cancelar = useMutation({
    mutationFn: () => cancelProject(project.id, motivo, notaMaterial, hableConTecnico),
    onSuccess: () => { setError(null); setAbierto(false); return refresh(); },
    onError: (err) => setError(apiErrorMessage(err)),
  });

  if (project.status === "cancelled") {
    return (
      <p className="acta-empty">
        Obra cancelada{project.cancelled_at
          ? ` el ${new Date(project.cancelled_at).toLocaleDateString("es-CO", { dateStyle: "medium" })}` : ""}
        {project.cancel_reason ? `: ${project.cancel_reason}` : "."}
      </p>
    );
  }
  if (!canCancel || project.status === "completed") return null;
  const material = chequeo?.material_in_field ?? [];
  const salidas = chequeo?.open_releases ?? [];
  const presencia = chequeo?.technician_presence ?? null;
  return (
    <div className="visits-step">
      {error && <p className="form-error" role="alert">{error}</p>}
      {!abierto ? (
        <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
          <button type="button" className="acta-btn is-small is-danger-quiet" onClick={() => setAbierto(true)}>Cancelar la obra…</button>
        </div>
      ) : (
        <form className="acta-reason" onSubmit={(e) => { e.preventDefault(); cancelar.mutate(); }}>
          <p className="acta-lead">
            La obra queda en solo lectura y el expediente se cierra. No se puede deshacer.
          </p>
          {presencia ? (
            <div className="form-error" role="alert">
              <strong>{presencia.technician_name} marcó «{presencia.label}» a las {presencia.at} en esta obra.</strong>
              <span> Si el cliente no estaba o desistió en la puerta, usa «No se pudo hacer la visita».</span>
              <label className="checkbox-row" style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "flex-start" }}>
                <input type="checkbox" checked={hableConTecnico} onChange={(e) => setHableConTecnico(e.target.checked)} />
                <span>Ya hablé con el técnico y sabe que no instala.</span>
              </label>
            </div>
          ) : chequeo?.install_today && (
            <p className="acta-note" role="status">
              La instalación es hoy: confirma con el técnico antes de cancelar.
            </p>
          )}
          {salidas.length > 0 && (
            <p className="acta-note" role="status">
              Se anulan solas, porque no han salido de bodega: {salidas.map((s) => `${s.number ?? "sin número"} (${s.status_label})`).join(", ")}.
            </p>
          )}
          {material.length > 0 && (
            <>
              <p className="acta-lead">
                Material entregado a la obra que no ha vuelto a bodega. Regístralo como devolución en
                Bodega › Movimientos, o explica qué pasó con él:
              </p>
              <ul>
                {material.map((m) => <li key={m.item_id}>{m.quantity} × {m.item_name}{m.sku ? ` (${m.sku})` : ""}</li>)}
              </ul>
              <label htmlFor="cancelar-material">Qué pasó con ese material</label>
              <input id="cancelar-material" minLength={5} value={notaMaterial}
                onChange={(e) => setNotaMaterial(e.target.value)} placeholder="Se quedó cortado en la casa" />
            </>
          )}
          <label htmlFor="cancelar-motivo">Por qué se cancela</label>
          <input id="cancelar-motivo" required minLength={5} value={motivo} autoFocus
            onChange={(e) => setMotivo(e.target.value)} placeholder="El cliente desistió del programa" />
          <div className="acta-actions">
            <button type="submit" className="acta-btn is-primary" disabled={cancelar.isPending || (Boolean(presencia) && !hableConTecnico)}>
              {cancelar.isPending ? "Cancelando…" : "Cancelar la obra"}
            </button>
            <button type="button" className="acta-btn is-quiet" onClick={() => setAbierto(false)}>Volver</button>
          </div>
        </form>
      )}
    </div>
  );
}

/**
 * «Si la visita no se puede hacer»: una sola tarjeta con la visita fallida y la
 * cancelación (QA de José, 31 oct). El técnico la marca desde su celular en la
 * obra y la oficina también puede; el límite de la organización va en una línea
 * discreta, no como un formulario más en cada obra.
 */
export function VisitOutcomeCard({ project, coords, canReport, canSchedule, canCancel }: {
  project: Project;
  coords: { latitude: number; longitude: number } | null;
  canReport: boolean;
  canSchedule: boolean;
  canCancel: boolean;
}) {
  const cerrada = project.status === "completed" || project.status === "cancelled";
  return (
    <section className="visit-box" aria-label="Si la visita no se puede hacer">
      <div className="visit-box-head">
        <div>
          <h4>Si la visita no se puede hacer</h4>
          {!cerrada && (
            <p>El técnico lo marca desde su celular en la obra (la oficina también puede). Si el cliente ya no
              quiere el programa, se cancela la obra.</p>
          )}
        </div>
        {canCancel && !cerrada && <VisitLimitSetting />}
      </div>
      <div className="visit-box-actions">
        <FailedVisitsStep project={project} coords={coords} canReport={canReport} canSchedule={canSchedule} />
        <CancelProjectStep project={project} canCancel={canCancel} />
      </div>
    </section>
  );
}

/** El límite de visitas fallidas de la organización (aplica a todas las obras). */
function VisitLimitSetting() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: visitKeys.settings, queryFn: getFieldOpsSettings });
  const [valor, setValor] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);
  const [editando, setEditando] = useState(false);
  const guardar = useMutation({
    mutationFn: () => saveFieldOpsSettings(Number(valor)),
    onSuccess: (s) => {
      setError(null); setGuardado(true); setValor(""); setEditando(false);
      queryClient.setQueryData(visitKeys.settings, s);
      return queryClient.invalidateQueries({ queryKey: ["project-visit-status"] });
    },
    onError: (err) => { setGuardado(false); setError(apiErrorMessage(err)); },
  });
  if (!data) return null;
  if (!editando) {
    return (
      <p className="visit-limit" title="Aplica a todas las obras">
        Límite: {data.max_failed_visits} visitas fallidas{guardado ? " · guardado" : ""} ·{" "}
        <button type="button" className="acta-link" onClick={() => setEditando(true)}>Cambiar</button>
      </p>
    );
  }
  return (
    <form className="visit-limit is-editing" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <label htmlFor="limite-visitas">Límite (todas las obras)</label>
      <input id="limite-visitas" type="number" inputMode="numeric" required min={data.min_failed_visits}
        max={data.max_allowed} value={valor} placeholder={String(data.max_failed_visits)} autoFocus
        onChange={(e) => { setValor(e.target.value); setGuardado(false); }} />
      <button type="submit" className="acta-btn is-small" disabled={guardar.isPending || !valor}>Guardar</button>
      <button type="button" className="acta-link" onClick={() => { setEditando(false); setValor(""); }}>Cancelar</button>
      {error && <p className="form-error" role="alert">{error}</p>}
    </form>
  );
}
