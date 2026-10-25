import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { askText, confirmAction } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { cancelShift, clockTime, copyWeek, createShifts, getSettings, hm, listPeople, listShifts, putSettings,
  SHIFT_STATUS_LABELS, type AttendanceSettings, type Shift } from "./api";
import { useMyAttendance } from "./useAttendance";
import "./attendance.css";

const DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];

function iso(d: Date): string {
  return d.toLocaleDateString("en-CA");
}
function lunesDe(d: Date): Date {
  const c = new Date(d);
  c.setHours(12, 0, 0, 0);
  c.setDate(c.getDate() - ((c.getDay() + 6) % 7));
  return c;
}
function mas(d: Date, n: number): Date {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
}
function apiError(e: unknown): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo guardar.";
}

/**
 * La malla de turnos: semana por persona, programar por persona o por grupo,
 * copiar la semana y las reglas de asistencia (tolerancias, extras, retención).
 */
export function ShiftPlannerPage() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puedeEditar = hasPermission("shifts.manage");
  const puedeReglas = hasPermission("attendance.review");
  // Las horas se muestran en la zona de la organización, no en la del navegador.
  const zona = useMyAttendance().data?.timezone;
  const [lunes, setLunes] = useState(() => lunesDe(new Date()));
  const desde = iso(lunes);
  const hasta = iso(mas(lunes, 6));
  const { data: gente } = useQuery({ queryKey: ["attendance-people"], queryFn: listPeople });
  const { data: turnos, isLoading } = useQuery({ queryKey: ["shifts", desde], queryFn: () => listShifts(desde, hasta) });

  const [form, setForm] = useState({ user_ids: [] as string[], date_from: desde, date_to: hasta,
    weekdays: [0, 1, 2, 3, 4], start_time: "07:00", end_time: "15:30", break_minutes: 30, notes: "" });
  const crear = useMutation({
    mutationFn: () => createShifts({ ...form, notes: form.notes || null }),
    onSuccess: (r) => {
      toast(`${r.created.length} turnos creados${r.skipped.length ? `, ${r.skipped.length} saltados por choque` : ""}`);
      qc.invalidateQueries({ queryKey: ["shifts"] });
    },
    onError: (e) => toast(apiError(e)),
  });
  const copiar = useMutation({
    mutationFn: () => copyWeek(desde, iso(mas(lunes, 7))),
    onSuccess: (r) => {
      toast(`Semana copiada: ${r.created} turnos${r.skipped ? `, ${r.skipped} saltados` : ""}`);
      qc.invalidateQueries({ queryKey: ["shifts"] });
    },
    onError: (e) => toast(apiError(e)),
  });

  const porPersona = useMemo(() => {
    const m = new Map<string, { nombre: string; dias: Shift[][] }>();
    for (const t of turnos ?? []) {
      const fila = m.get(t.user_id) ?? { nombre: t.user_name ?? "—", dias: Array.from({ length: 7 }, () => []) };
      const i = Math.round((new Date(`${t.shift_date}T12:00:00`).getTime() - lunes.getTime()) / 864e5);
      if (i >= 0 && i < 7) fila.dias[i].push(t);
      m.set(t.user_id, fila);
    }
    return [...m.entries()].sort((a, b) => a[1].nombre.localeCompare(b[1].nombre));
  }, [turnos, lunes]);

  const cancelar = async (t: Shift) => {
    const motivo = await askText({ title: `Cancelar el turno de ${t.user_name} del ${t.shift_date}`,
      label: "Motivo", required: true, confirmLabel: "Cancelar turno", danger: true });
    if (!motivo) return;
    try {
      await cancelShift(t.id, motivo);
      toast("Turno cancelado");
      qc.invalidateQueries({ queryKey: ["shifts"] });
    } catch (e) {
      toast(apiError(e));
    }
  };

  return (
    <div className="att-page is-wide">
      <PageHeader title="Malla de turnos" description="Quién trabaja cada día, en qué horario y en qué obra."
        actions={puedeEditar ? <button type="button" className="att-btn" disabled={copiar.isPending}
          onClick={async () => {
            if (await confirmAction({ title: "Copiar esta semana a la siguiente",
              message: "Los turnos que choquen con otros ya programados se saltan.", confirmLabel: "Copiar" }))
              copiar.mutate();
          }}>Copiar a la semana siguiente</button> : undefined} />

      <div className="att-weeknav">
        <button type="button" className="att-btn" onClick={() => setLunes(mas(lunes, -7))}>← Semana anterior</button>
        <strong>{lunes.toLocaleDateString("es-US", { day: "numeric", month: "short" })} – {
          mas(lunes, 6).toLocaleDateString("es-US", { day: "numeric", month: "short", year: "numeric" })}</strong>
        <button type="button" className="att-btn" onClick={() => setLunes(mas(lunes, 7))}>Semana siguiente →</button>
      </div>

      <div className="att-scroll">
        <table className="att-week">
          <thead>
            <tr><th scope="col">Persona</th>{DIAS.map((d, i) => (
              <th key={d} scope="col">{d} {mas(lunes, i).getDate()}</th>))}</tr>
          </thead>
          <tbody>
            {isLoading && <tr><td colSpan={8}>Cargando…</td></tr>}
            {!isLoading && !porPersona.length && <tr><td colSpan={8} className="att-muted">
              No hay turnos esta semana. Prográmalos abajo.</td></tr>}
            {porPersona.map(([uid, fila]) => (
              <tr key={uid}>
                <th scope="row">{fila.nombre}</th>
                {fila.dias.map((ts, i) => (
                  <td key={i}>
                    {ts.map((t) => (
                      <div key={t.id} className={`att-shift is-${t.compliance}`}>
                        <span>{clockTime(t.starts_at, zona)}–{clockTime(t.ends_at, zona)}</span>
                        {t.project_title && <small>{t.project_title}</small>}
                        <small>{SHIFT_STATUS_LABELS[t.compliance ?? ""] ?? ""}</small>
                        {puedeEditar && !t.entry_id && (
                          <button type="button" className="att-x" aria-label={`Cancelar turno del ${t.shift_date}`}
                            onClick={() => void cancelar(t)}>×</button>
                        )}
                      </div>
                    ))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {puedeEditar && (
        <section className="att-card" aria-labelledby="att-programar">
          <h2 id="att-programar">Programar turnos</h2>
          <form className="att-form" onSubmit={(e) => { e.preventDefault(); crear.mutate(); }}>
            <fieldset className="att-people">
              <legend>Personas ({form.user_ids.length})</legend>
              {(gente ?? []).map((p) => (
                <label key={p.id} className="att-check">
                  <input type="checkbox" checked={form.user_ids.includes(p.id)} onChange={(e) => setForm({ ...form,
                    user_ids: e.target.checked ? [...form.user_ids, p.id] : form.user_ids.filter((x) => x !== p.id) })} />
                  {p.full_name}
                </label>
              ))}
            </fieldset>
            <div className="att-form-row">
              <label>Desde<input type="date" value={form.date_from} onChange={(e) => setForm({ ...form, date_from: e.target.value })} /></label>
              <label>Hasta<input type="date" value={form.date_to} onChange={(e) => setForm({ ...form, date_to: e.target.value })} /></label>
            </div>
            <fieldset className="att-days">
              <legend>Días</legend>
              {DIAS.map((d, i) => (
                <label key={d} className="att-check">
                  <input type="checkbox" checked={form.weekdays.includes(i)} onChange={(e) => setForm({ ...form,
                    weekdays: e.target.checked ? [...form.weekdays, i] : form.weekdays.filter((x) => x !== i) })} />{d}
                </label>
              ))}
            </fieldset>
            <div className="att-form-row">
              <label>Entrada<input type="time" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} /></label>
              <label>Salida<input type="time" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} /></label>
              <label>Descanso (min)<input type="number" min={0} max={480} value={form.break_minutes}
                onChange={(e) => setForm({ ...form, break_minutes: Number(e.target.value) })} /></label>
            </div>
            <p className="att-muted">Si la salida es antes que la entrada, el turno termina al día siguiente (nocturno).</p>
            <label>Nota<input value={form.notes} maxLength={255} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
            <div className="att-actions">
              <button type="submit" className="att-btn is-primary" disabled={!form.user_ids.length || crear.isPending}>
                {crear.isPending ? "Programando…" : "Programar turnos"}</button>
            </div>
          </form>
        </section>
      )}

      {puedeReglas && <SettingsPanel />}
    </div>
  );
}

function SettingsPanel() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["attendance-settings"], queryFn: getSettings });
  const [draft, setDraft] = useState<Partial<AttendanceSettings>>({});
  const v = { ...data, ...draft } as AttendanceSettings;
  const guardar = useMutation({
    mutationFn: () => putSettings(draft),
    onSuccess: () => { toast("Reglas guardadas"); setDraft({}); qc.invalidateQueries({ queryKey: ["attendance-settings"] }); },
    onError: (e) => toast(apiError(e)),
  });
  if (!data) return null;
  const num = (k: keyof AttendanceSettings, label: string, max: number, nota?: string) => (
    <label>{label}<input type="number" min={0} max={max} value={Number(v[k])}
      onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} />{nota && <small>{nota}</small>}</label>
  );
  return (
    <section className="att-card" aria-labelledby="att-reglas">
      <h2 id="att-reglas">Reglas de asistencia</h2>
      <p className="att-muted">Valores por defecto mientras Don Aldo confirma: tolerancia de 10 min, extras desde
        8 h al día y 40 h a la semana, ubicación por eventos y borrado de coordenadas a los 90 días.</p>
      <form className="att-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
        <div className="att-form-row">
          {num("late_tolerance_minutes", "Tolerancia de entrada (min)", 240)}
          {num("early_leave_tolerance_minutes", "Tolerancia de salida (min)", 240)}
        </div>
        <div className="att-form-row">
          {num("daily_overtime_after_minutes", "Extras desde (min al día)", 1440, `${hm(v.daily_overtime_after_minutes)} · 0 apaga`)}
          {num("weekly_overtime_after_minutes", "Extras desde (min a la semana)", 10080, `${hm(v.weekly_overtime_after_minutes)} · 0 apaga`)}
        </div>
        <div className="att-form-row">
          {num("tracking_interval_minutes", "Ubicación con la app abierta cada (min)", 240, "0 = solo en las marcas")}
          {num("location_retention_days", "Borrar coordenadas a los (días)", 730)}
        </div>
        <label className="att-check"><input type="checkbox" checked={v.paid_pauses}
          onChange={(e) => setDraft({ ...draft, paid_pauses: e.target.checked })} /> Las pausas se pagan</label>
        <label className="att-check"><input type="checkbox" checked={v.require_clock_in_for_field_work}
          onChange={(e) => setDraft({ ...draft, require_clock_in_for_field_work: e.target.checked })} />
          Bloquear evidencias, checklist y diario hasta que el técnico inicie su turno</label>
        <div className="att-actions">
          <button type="submit" className="att-btn is-primary" disabled={!Object.keys(draft).length || guardar.isPending}>
            Guardar reglas</button>
        </div>
      </form>
    </section>
  );
}
