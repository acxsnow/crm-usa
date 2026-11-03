import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { PageHeader } from "@/components/ui/PageHeader";
import { apiClient } from "@/lib/apiClient";
import { toast } from "@/lib/toast";
import { apiErrorMessage, localISODate, scheduleInstallation } from "./module5Api";
import "./dispatch.css";

interface Job {
  project_id: string;
  title: string;
  status: string;
  scheduled_date: string | null;
  technician_id: string | null;
  address: string | null;
  case_number: string | null;
  days_late: number | null;
}
interface Shift { starts_at: string; ends_at: string }
interface Board {
  days: string[];
  today: string;
  technicians: { id: string; name: string; jobs: Record<string, Job[]>; shifts: Record<string, Shift[]> }[];
  unassigned_in_range: Record<string, Job[]>;
  unscheduled: Job[];
}
type Vista = "day" | "week";

const sumar = (iso: string, dias: number) => {
  const d = new Date(`${iso}T12:00:00`);
  d.setDate(d.getDate() + dias);
  return localISODate(d);
};
const lunes = (iso: string) => {
  const d = new Date(`${iso}T12:00:00`);
  return sumar(iso, -((d.getDay() + 6) % 7));
};
const cabecera = (iso: string) =>
  new Date(`${iso}T12:00:00`).toLocaleDateString("es-CO", { weekday: "short", day: "numeric", month: "short" });
const hora = (iso: string) => new Date(iso).toLocaleTimeString("es-CO", { hour: "numeric", minute: "2-digit" });

/**
 * Despacho (como el «Dispatch» de Housecall Pro): una fila por técnico y una
 * columna por día, con su turno de la malla. Se arrastra una obra a la celda,
 * o se toca para elegir técnico y fecha (en el celular no hay arrastre).
 */
export function DispatchBoardPage() {
  const qc = useQueryClient();
  const [vista, setVista] = useState<Vista>(() => (window.innerWidth < 768 ? "day" : "week"));
  const [ancla, setAncla] = useState(localISODate());
  const [abierta, setAbierta] = useState<Job | null>(null);
  const desde = vista === "week" ? lunes(ancla) : ancla;
  const hasta = vista === "week" ? sumar(desde, 6) : ancla;
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dispatch-board", desde, hasta],
    queryFn: async () => (await apiClient.get<Board>("/dispatch/board", { params: { date_from: desde, date_to: hasta } })).data,
  });
  const asignar = useMutation({
    mutationFn: (v: { job: Job; technician: string; date: string }) =>
      scheduleInstallation(v.job.project_id, { technician_user_id: v.technician, scheduled_date: v.date }),
    onSuccess: () => { setAbierta(null); return qc.invalidateQueries({ queryKey: ["dispatch-board"] }); },
    onError: (e) => toast(apiErrorMessage(e)),
  });
  const soltar = (e: React.DragEvent, technician: string, date: string) => {
    e.preventDefault();
    const crudo = e.dataTransfer.getData("application/json");
    if (crudo) asignar.mutate({ job: JSON.parse(crudo) as Job, technician, date });
  };
  const sinTecnico = useMemo(() => Object.values(data?.unassigned_in_range ?? {}).flat(), [data]);
  const bandeja = useMemo(() => {
    const vistos = new Set(sinTecnico.map((j) => j.project_id));
    return [...sinTecnico, ...(data?.unscheduled ?? []).filter((j) => !vistos.has(j.project_id))];
  }, [data, sinTecnico]);

  return (
    <div className="dispatch-page">
      <PageHeader eyebrow="Operación de campo" title="Despacho"
        description="Planea los próximos días por técnico: arrastra una obra a su celda o tócala para elegir técnico y fecha." />
      <div className="dispatch-toolbar">
        <div className="dispatch-nav">
          <button type="button" className="acta-btn" aria-label="Anterior" onClick={() => setAncla(sumar(ancla, vista === "week" ? -7 : -1))}>‹</button>
          <button type="button" className="acta-btn" onClick={() => setAncla(localISODate())}>Hoy</button>
          <button type="button" className="acta-btn" aria-label="Siguiente" onClick={() => setAncla(sumar(ancla, vista === "week" ? 7 : 1))}>›</button>
          <input type="date" aria-label="Ir a la fecha" value={ancla} onChange={(e) => e.target.value && setAncla(e.target.value)} />
        </div>
        <div className="dispatch-views" role="group" aria-label="Vista">
          {([["day", "Día"], ["week", "Semana"]] as [Vista, string][]).map(([k, l]) => (
            <button key={k} type="button" aria-pressed={vista === k} className={vista === k ? "is-on" : undefined} onClick={() => setVista(k)}>{l}</button>
          ))}
        </div>
      </div>

      {isLoading && <p className="acta-empty">Cargando el tablero…</p>}
      {isError && <p className="form-error" role="alert">No se pudo cargar el tablero.</p>}
      {data && (
        <>
          {data.technicians.length === 0 ? <p className="acta-empty">No hay técnicos activos.</p> : (
            <div className="dispatch-scroll">
              <table className="dispatch-grid">
                <thead>
                  <tr>
                    <th scope="col">Técnico</th>
                    {data.days.map((d) => <th scope="col" key={d} className={d === data.today ? "is-today" : undefined}>{cabecera(d)}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {data.technicians.map((t) => (
                    <tr key={t.id}>
                      <th scope="row">{t.name}</th>
                      {data.days.map((d) => (
                        <td key={d} className={d === data.today ? "is-today" : undefined}
                          onDragOver={(e) => e.preventDefault()} onDrop={(e) => soltar(e, t.id, d)}>
                          {(t.shifts[d] ?? []).map((s, i) => <small key={i} className="dispatch-shift">{hora(s.starts_at)} – {hora(s.ends_at)}</small>)}
                          {(t.jobs[d] ?? []).map((j) => <JobChip key={j.project_id} job={j} onOpen={setAbierta} />)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <section className="dispatch-tray" aria-labelledby="dispatch-sin-agendar">
            <h3 id="dispatch-sin-agendar">Sin agendar <span className="annex-count">{bandeja.length}</span></h3>
            {bandeja.length === 0 ? <p className="acta-empty">Todas las obras abiertas tienen técnico y fecha.</p> : (
              <div className="dispatch-tray-list">
                {bandeja.map((j) => <JobChip key={j.project_id} job={j} onOpen={setAbierta} />)}
              </div>
            )}
          </section>
        </>
      )}
      {abierta && data && (
        <AssignDialog job={abierta} technicians={data.technicians} defaultDate={ancla} saving={asignar.isPending}
          onClose={() => setAbierta(null)} onSave={(technician, date) => asignar.mutate({ job: abierta, technician, date })} />
      )}
    </div>
  );
}

function JobChip({ job, onOpen }: { job: Job; onOpen: (j: Job) => void }) {
  return (
    <button type="button" draggable className={`dispatch-job${job.days_late ? " is-late" : ""}`} onClick={() => onOpen(job)}
      onDragStart={(e) => e.dataTransfer.setData("application/json", JSON.stringify(job))}>
      <strong>{job.title}</strong>
      {job.address && <small>{job.address}</small>}
      {!!job.days_late && <small className="dispatch-late">{job.days_late} {job.days_late === 1 ? "día" : "días"} de atraso</small>}
    </button>
  );
}

function AssignDialog({ job, technicians, defaultDate, saving, onClose, onSave }: {
  job: Job;
  technicians: Board["technicians"];
  defaultDate: string;
  saving: boolean;
  onClose: () => void;
  onSave: (technician: string, date: string) => void;
}) {
  const [tecnico, setTecnico] = useState(job.technician_id ?? "");
  const [fecha, setFecha] = useState(job.scheduled_date ?? defaultDate);
  return (
    <div className="dispatch-dialog" role="dialog" aria-modal="true" aria-labelledby="dispatch-dialog-title">
      <form className="dispatch-dialog-card" onSubmit={(e) => { e.preventDefault(); onSave(tecnico, fecha); }}>
        <h3 id="dispatch-dialog-title">{job.title}</h3>
        {job.address && <p className="acta-lead">{job.address}</p>}
        <label className="form-label" htmlFor="dispatch-tecnico">Técnico</label>
        <select id="dispatch-tecnico" required value={tecnico} onChange={(e) => setTecnico(e.target.value)}>
          <option value="">Elige…</option>
          {technicians.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        <label className="form-label" htmlFor="dispatch-fecha">Fecha</label>
        <input id="dispatch-fecha" type="date" required min={localISODate()} value={fecha} onChange={(e) => setFecha(e.target.value)} />
        <div className="acta-actions">
          <Link className="acta-btn is-quiet" to={`/projects/${job.project_id}`}>Ver obra</Link>
          <button type="button" className="acta-btn" onClick={onClose}>Cancelar</button>
          <button type="submit" className="acta-btn is-primary" disabled={saving}>{saving ? "Guardando…" : "Agendar"}</button>
        </div>
      </form>
    </div>
  );
}
