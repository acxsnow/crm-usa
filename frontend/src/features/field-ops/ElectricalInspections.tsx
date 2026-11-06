import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "@/components/ui/PageHeader";
import { useAuth } from "@/features/auth/AuthContext";
import { apiClient } from "@/lib/apiClient";
import { toast } from "@/lib/toast";
import { apiErrorMessage, localISODate, useInstallers } from "./module5Api";
import "./dispatch.css";

/**
 * Inspección eléctrica (cliente, 5 nov 2026): la visita del técnico antes de la
 * instalación que dice si la casa es viable y a qué beneficios aplica. La
 * agenda Administración desde el expediente; el técnico registra el resultado
 * desde «Inspecciones eléctricas».
 */
export interface ElectricalInspection {
  id: string;
  case_id: string;
  case_number: string | null;
  address: string | null;
  customer_name: string | null;
  technician_user_id: string;
  technician_name: string | null;
  scheduled_date: string;
  status: "scheduled" | "done" | "cancelled";
  status_label: string;
  notes: string | null;
  panel_amperage: string | null;
  viability: "adequate" | "needs_upgrade" | "not_viable" | null;
  viability_label: string | null;
  tons: string | null;
  water_heater_eligible: boolean | null;
  induction_eligible: boolean | null;
  result_notes: string | null;
  completed_at: string | null;
  cancel_reason: string | null;
}

const AMPERAJE: [string, string][] = [["50", "50 A"], ["70", "70 A"], ["100", "100 A"], ["125", "125 A"],
  ["150", "150 A"], ["200", "200 A"], ["other", "Otro / no se sabe"]];
const VIABILIDAD: [string, string][] = [["adequate", "Adecuada"], ["needs_upgrade", "Requiere adecuación"],
  ["not_viable", "No viable"]];

const caseKey = (caseId: string) => ["electrical-inspections", "case", caseId];
const dia = (iso: string) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" });
const siNo = (v: boolean | null) => (v === null ? "—" : v ? "Sí" : "No");

function Resultado({ ins }: { ins: ElectricalInspection }) {
  return (
    <dl className="electrical-result">
      <div><dt>Viabilidad</dt><dd className={ins.viability === "not_viable" ? "is-bad" : undefined}>{ins.viability_label}</dd></div>
      <div><dt>Panel</dt><dd>{AMPERAJE.find(([v]) => v === ins.panel_amperage)?.[1] ?? "—"}</dd></div>
      <div><dt>Toneladas</dt><dd>{ins.tons ?? "—"}</dd></div>
      <div><dt>Calentador de agua</dt><dd>{siNo(ins.water_heater_eligible)}</dd></div>
      <div><dt>Cocina de inducción</dt><dd>{siNo(ins.induction_eligible)}</dd></div>
      {ins.result_notes && <div className="is-wide"><dt>Notas</dt><dd>{ins.result_notes}</dd></div>}
    </dl>
  );
}

/** La tarjeta del expediente (revisión): agendar, ver el resultado y cancelar. */
export function CaseElectricalInspection({ caseId, canSchedule }: { caseId: string; canSchedule: boolean }) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: caseKey(caseId),
    queryFn: async () => (await apiClient.get<ElectricalInspection[]>(`/cases/${caseId}/electrical-inspections`)).data,
  });
  const { data: tecnicos } = useInstallers(canSchedule);
  const [tecnico, setTecnico] = useState("");
  const [fecha, setFecha] = useState(localISODate());
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const refrescar = () => qc.invalidateQueries({ queryKey: ["electrical-inspections"] });
  const agendar = useMutation({
    mutationFn: async () => (await apiClient.post(`/cases/${caseId}/electrical-inspections`, {
      technician_user_id: tecnico, scheduled_date: fecha, notes: notas || null })).data,
    onSuccess: () => { setError(null); setNotas(""); return refrescar(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const cancelar = useMutation({
    mutationFn: async (v: { id: string; reason: string }) =>
      (await apiClient.post(`/electrical-inspections/${v.id}/cancel`, { reason: v.reason })).data,
    onSuccess: refrescar,
    onError: (e) => toast(apiErrorMessage(e)),
  });
  const lista = data ?? [];
  const abierta = lista.find((i) => i.status === "scheduled");
  const ultima = [...lista].reverse().find((i) => i.status === "done");

  return (
    <article className="acta electrical-card">
      <h2>Inspección eléctrica</h2>
      <p className="review-hint">La visita del técnico antes de instalar: si la casa es viable, cuántas toneladas y si
        califica para calentador de agua o cocina de inducción.</p>
      {ultima && (
        <>
          {ultima.viability === "not_viable" && (
            <p className="form-error" role="alert">El técnico dice que la casa no es viable.</p>
          )}
          <p className="electrical-meta">Hecha por {ultima.technician_name} el {dia(ultima.scheduled_date)}</p>
          <Resultado ins={ultima} />
        </>
      )}
      {abierta && (
        <div className="electrical-open">
          <p><strong>Agendada</strong> para el {dia(abierta.scheduled_date)} con {abierta.technician_name}.</p>
          {canSchedule && (
            <button type="button" className="acta-btn is-quiet" disabled={cancelar.isPending} onClick={() => {
              const motivo = window.prompt("¿Por qué se cancela la inspección eléctrica?");
              if (motivo) cancelar.mutate({ id: abierta.id, reason: motivo });
            }}>Cancelar</button>
          )}
        </div>
      )}
      {!abierta && canSchedule && (
        <form className="review-form" onSubmit={(e) => { e.preventDefault(); agendar.mutate(); }}>
          <div className="form-field">
            <label className="form-label" htmlFor="ei-tecnico">{ultima ? "Agendar otra con" : "Técnico"}</label>
            <select id="ei-tecnico" required value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
              <option value="">Elige…</option>
              {(tecnicos ?? []).map((t) => <option key={t.id} value={t.id}>{t.full_name}</option>)}
            </select>
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="ei-fecha">Fecha</label>
            <input id="ei-fecha" type="date" required min={localISODate()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
          </div>
          <div className="form-field">
            <label className="form-label" htmlFor="ei-notas">Notas para el técnico <span className="optional">(opcional)</span></label>
            <input id="ei-notas" value={notas} onChange={(e) => setNotas(e.target.value)} />
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <button type="submit" className="acta-btn is-primary" disabled={agendar.isPending || !tecnico}>
            {agendar.isPending ? "Agendando…" : "Agendar inspección eléctrica"}</button>
        </form>
      )}
      {!abierta && !ultima && !canSchedule && <p className="acta-empty">Sin inspección eléctrica.</p>}
    </article>
  );
}

function ResultForm({ ins, onDone }: { ins: ElectricalInspection; onDone: () => void }) {
  const [viabilidad, setViabilidad] = useState(ins.viability ?? "");
  const [amperaje, setAmperaje] = useState(ins.panel_amperage ?? "");
  const [toneladas, setToneladas] = useState(ins.tons ?? "");
  const [calentador, setCalentador] = useState<boolean | null>(ins.water_heater_eligible);
  const [induccion, setInduccion] = useState<boolean | null>(ins.induction_eligible);
  const [notas, setNotas] = useState(ins.result_notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const guardar = useMutation({
    mutationFn: async () => (await apiClient.post(`/electrical-inspections/${ins.id}/result`, {
      viability: viabilidad, panel_amperage: amperaje || null, tons: toneladas || null,
      water_heater_eligible: calentador, induction_eligible: induccion, result_notes: notas || null })).data,
    onSuccess: () => { setError(null); onDone(); },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const SiNo = ({ name, value, onChange }: { name: string; value: boolean | null; onChange: (v: boolean) => void }) => (
    <div className="electrical-yesno" role="radiogroup">
      {([[true, "Sí"], [false, "No"]] as [boolean, string][]).map(([v, l]) => (
        <label key={l}><input type="radio" name={name} checked={value === v} onChange={() => onChange(v)} /> {l}</label>
      ))}
    </div>
  );
  return (
    <form className="electrical-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <fieldset className="form-field">
        <legend className="form-label">¿La casa es viable? *</legend>
        <div className="electrical-yesno">
          {VIABILIDAD.map(([v, l]) => (
            <label key={v}><input type="radio" name={`via-${ins.id}`} checked={viabilidad === v} onChange={() => setViabilidad(v)} /> {l}</label>
          ))}
        </div>
      </fieldset>
      <div className="form-field">
        <label className="form-label" htmlFor={`amp-${ins.id}`}>Amperaje del panel</label>
        <select id={`amp-${ins.id}`} value={amperaje} onChange={(e) => setAmperaje(e.target.value)}>
          <option value="">Elige…</option>
          {AMPERAJE.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <div className="form-field">
        <label className="form-label" htmlFor={`ton-${ins.id}`}>Toneladas del aire</label>
        <input id={`ton-${ins.id}`} type="number" min="0.5" max="10" step="0.5" inputMode="decimal" value={toneladas}
          onChange={(e) => setToneladas(e.target.value)} />
      </div>
      <fieldset className="form-field">
        <legend className="form-label">¿Califica para calentador de agua?</legend>
        <SiNo name={`cal-${ins.id}`} value={calentador} onChange={setCalentador} />
      </fieldset>
      <fieldset className="form-field">
        <legend className="form-label">¿Califica para cocina de inducción?</legend>
        <SiNo name={`ind-${ins.id}`} value={induccion} onChange={setInduccion} />
      </fieldset>
      <div className="form-field">
        <label className="form-label" htmlFor={`not-${ins.id}`}>
          Notas {viabilidad === "not_viable" ? "(por qué no es viable) *" : <span className="optional">(opcional)</span>}</label>
        <textarea id={`not-${ins.id}`} rows={3} value={notas} onChange={(e) => setNotas(e.target.value)} />
      </div>
      {error && <p className="form-error" role="alert">{error}</p>}
      <button type="submit" className="acta-btn is-primary" disabled={!viabilidad || guardar.isPending}>
        {guardar.isPending ? "Guardando…" : "Guardar resultado"}</button>
    </form>
  );
}

/** «Inspecciones eléctricas»: el técnico ve las suyas; quien despacha, todas. */
export function ElectricalInspectionsPage() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const verExpediente = hasPermission("cases.review");
  const [estado, setEstado] = useState("scheduled");
  const [abierta, setAbierta] = useState<string | null>(null);
  const { data, isLoading } = useQuery({
    queryKey: ["electrical-inspections", "list", estado],
    queryFn: async () => {
      const r = await apiClient.get<ElectricalInspection[]>("/electrical-inspections",
        { params: { status: estado || undefined, limit: 500 } });
      return { items: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) };
    },
  });
  const lista = data?.items;
  return (
    <div className="electrical-page">
      <PageHeader eyebrow="Operación de campo" title="Inspecciones eléctricas"
        description="La visita antes de instalar: si la casa es viable y a qué beneficios aplica. Se agenda desde la revisión del expediente." />
      <div className="notices-toolbar">
        <select aria-label="Estado" value={estado} onChange={(e) => setEstado(e.target.value)}>
          <option value="scheduled">Por hacer</option><option value="done">Hechas</option>
          <option value="cancelled">Canceladas</option><option value="">Todas</option>
        </select>
      </div>
      {isLoading && <p className="acta-empty">Cargando…</p>}
      {lista?.length === 0 && <p className="acta-empty">No hay inspecciones eléctricas con este filtro.</p>}
      {data && data.total > data.items.length && (
        <p className="review-hint">Se muestran las {data.items.length} más recientes de {data.total}. Filtra por estado para ver las demás.</p>
      )}
      <ul className="electrical-list">
        {(lista ?? []).map((i) => (
          <li key={i.id} className="acta electrical-item">
            <header>
              <div>
                <strong>{i.customer_name ?? i.case_number}</strong>
                <span>{i.address}</span>
                <span>{dia(i.scheduled_date)} · {i.technician_name} · {i.case_number}</span>
              </div>
              <span className={`electrical-chip is-${i.status}`}>{i.status_label}</span>
            </header>
            {i.notes && <p className="review-hint">{i.notes}</p>}
            {i.status === "done" && <Resultado ins={i} />}
            {i.status === "cancelled" && <p className="review-hint">Cancelada: {i.cancel_reason}</p>}
            {i.status !== "cancelled" && (abierta === i.id
              ? <ResultForm ins={i} onDone={() => { setAbierta(null); void qc.invalidateQueries({ queryKey: ["electrical-inspections"] }); }} />
              : (
                <div className="acta-actions" style={{ justifyContent: "flex-start" }}>
                  <button type="button" className="acta-btn is-primary" onClick={() => setAbierta(i.id)}>
                    {i.status === "done" ? "Corregir resultado" : "Registrar resultado"}</button>
                  {verExpediente && <Link className="acta-btn is-quiet" to={`/cases/${i.case_id}/review`}>Ver expediente</Link>}
                </div>
              ))}
          </li>
        ))}
      </ul>
    </div>
  );
}
