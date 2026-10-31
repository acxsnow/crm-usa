import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/ui/PageHeader";
import { askText, confirmAction } from "@/components/ui/ConfirmDialog";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { createPeriod, downloadPayroll, getPayroll, hm, listPeriods, setPeriodStatus } from "./api";
import { PaginatedTable } from "@/components/DataTable";
import { useClientPagination } from "@/lib/useClientPagination";
import "./attendance.css";

function iso(d: Date): string {
  return d.toLocaleDateString("en-CA");
}
function apiError(e: unknown): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo guardar.";
}

/**
 * Lo que Don Aldo revisa antes de cruzarlo con la nómina: horas programadas,
 * registradas, aprobadas, extras, ausencias y novedades por persona. No calcula
 * pagos ni descuentos.
 */
export function PayrollPage() {
  const qc = useQueryClient();
  const { hasPermission } = useAuth();
  const puedeCerrar = hasPermission("payroll.close");
  const hoy = new Date();
  const lunes = new Date(hoy);
  lunes.setDate(hoy.getDate() - ((hoy.getDay() + 6) % 7) - 7);
  const [desde, setDesde] = useState(iso(lunes));
  const [hasta, setHasta] = useState(iso(new Date(lunes.getTime() + 13 * 864e5)));
  const { data, isLoading } = useQuery({ queryKey: ["payroll", desde, hasta], queryFn: () => getPayroll(desde, hasta) });
  const { data: periodos } = useQuery({ queryKey: ["payroll-periods"], queryFn: listPeriods });
  // La nómina del rango llega calculada completa: se pagina aquí y el total suma a todos.
  const empleados = useClientPagination(data?.rows, isLoading);
  const refrescar = () => { qc.invalidateQueries({ queryKey: ["payroll"] }); qc.invalidateQueries({ queryKey: ["payroll-periods"] }); };
  const crear = useMutation({ mutationFn: () => createPeriod(desde, hasta), onSuccess: () => { toast("Período creado"); refrescar(); },
    onError: (e) => toast(apiError(e)) });
  const estado = useMutation({
    mutationFn: ({ id, cerrar, motivo }: { id: string; cerrar: boolean; motivo?: string }) => setPeriodStatus(id, cerrar, motivo),
    onSuccess: (p) => { toast(p.status === "closed" ? "Período cerrado" : "Período reabierto"); refrescar(); },
    onError: (e) => toast(apiError(e)),
  });
  const total = (k: keyof NonNullable<typeof data>["rows"][number]) =>
    (data?.rows ?? []).reduce((s, r) => s + Number(r[k] ?? 0), 0);
  const actual = (periodos ?? []).find((p) => p.start_date === desde && p.end_date === hasta);

  return (
    <div className="att-page is-wide">
      <PageHeader title="Reporte para nómina" description="Revísalo antes de pasarlo a nómina. Este reporte no calcula pagos ni descuentos."
        actions={<>
          <button type="button" className="att-btn" onClick={() => void downloadPayroll("xlsx", desde, hasta)}>Excel</button>
          <button type="button" className="att-btn" onClick={() => void downloadPayroll("pdf", desde, hasta)}>PDF</button>
        </>} />
      <div className="att-filters">
        <label className="att-field">Desde<input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></label>
        <label className="att-field">Hasta<input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></label>
        <p className="att-muted">Período: <strong>{data?.period_status ?? "—"}</strong>
          {data && <> · Extras desde {hm(data.rules.daily_overtime_after_minutes)} al día y {
            hm(data.rules.weekly_overtime_after_minutes)} a la semana · pausas {data.rules.paid_pauses ? "pagadas" : "no pagadas"}</>}</p>
        {puedeCerrar && !actual && <button type="button" className="att-btn" onClick={() => crear.mutate()}>Crear período con estas fechas</button>}
        {puedeCerrar && actual && actual.status === "open" && (
          <button type="button" className="att-btn is-primary" onClick={async () => {
            if (await confirmAction({ title: "Cerrar el período", message: "Nadie podrá marcar, corregir ni aprobar horas de estas fechas hasta reabrirlo.",
              confirmLabel: "Cerrar período" })) estado.mutate({ id: actual.id, cerrar: true });
          }}>Cerrar período</button>
        )}
        {puedeCerrar && actual && actual.status === "closed" && (
          <button type="button" className="att-btn" onClick={async () => {
            const motivo = await askText({ title: "Reabrir el período", label: "Motivo", required: true, confirmLabel: "Reabrir" });
            if (motivo) estado.mutate({ id: actual.id, cerrar: false, motivo });
          }}>Reabrir período</button>
        )}
      </div>

      <section className="att-card">
        <PaginatedTable list={empleados} getRowKey={(r) => r.user_id} className="att-table is-numbers" emptyMessage="Sin datos en el rango."
          columns={[
            { key: "empleado", header: "Empleado", render: (r) => <strong>{r.user_name}</strong> },
            { key: "programadas", header: "Programadas", render: (r) => hm(r.scheduled_minutes) },
            { key: "registradas", header: "Registradas", render: (r) => hm(r.recorded_minutes) },
            { key: "pausas", header: "Pausas", render: (r) => hm(r.pause_minutes) },
            { key: "extras_dia", header: "Extras día", render: (r) => hm(r.daily_overtime_minutes) },
            { key: "extras_semana", header: "Extras semana", render: (r) => hm(r.weekly_overtime_minutes) },
            { key: "aprobadas", header: "Aprobadas", render: (r) => <strong>{hm(r.approved_minutes)}</strong> },
            { key: "ausencias", header: "Ausencias", render: (r) => r.absences },
            { key: "tarde", header: "Tarde", render: (r) => r.late_arrivals },
            { key: "antes", header: "Salió antes", render: (r) => r.early_departures },
            { key: "correcciones", header: "Correcciones", render: (r) => r.corrections },
            { key: "novedades", header: "Novedades", render: (r) => r.novelties },
            { key: "sin_salida", header: "Sin salida", render: (r) => <span className={r.open_entries ? "att-warn" : ""}>{r.open_entries}</span> },
            { key: "sin_aprobar", header: "Sin aprobar", render: (r) => <span className={r.unapproved_entries ? "att-warn" : ""}>{r.unapproved_entries}</span> },
          ]}
          footer={["Total", hm(total("scheduled_minutes")), hm(total("recorded_minutes")), hm(total("pause_minutes")),
            hm(total("daily_overtime_minutes")), hm(total("weekly_overtime_minutes")), hm(total("approved_minutes")),
            total("absences"), total("late_arrivals"), total("early_departures"), total("corrections"), total("novelties"),
            total("open_entries"), total("unapproved_entries")]} />
        <p className="att-muted">«Ausencias» son turnos vencidos sin marcación: confírmalas con la persona antes de descontar.</p>
      </section>

      <section className="att-card" aria-labelledby="att-periodos">
        <h2 id="att-periodos">Períodos</h2>
        {!(periodos ?? []).length && <p className="att-muted">Todavía no hay períodos.</p>}
        <ul className="att-list">
          {(periodos ?? []).map((p) => (
            <li key={p.id}><button type="button" className="att-btn is-link" onClick={() => { setDesde(p.start_date); setHasta(p.end_date); }}>
              {p.start_date} a {p.end_date}</button> · <span className={`att-pill is-${p.status}`}>{p.status === "closed" ? "Cerrado" : "Abierto"}</span>
              <small>{p.history.map((h) => ` · ${h.action === "created" ? "creado" : h.action === "closed" ? "cerrado" : "reabierto"} por ${h.by}${
                h.reason ? ` (${h.reason})` : ""}`).join("")}</small></li>
          ))}
        </ul>
      </section>
    </div>
  );
}
