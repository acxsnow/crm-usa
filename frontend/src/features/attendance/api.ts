/**
 * Turnos, asistencia, nómina y mapa operativo (spec
 * `docs/superpowers/specs/2026-10-24-turnos-mapa-design.md`).
 */
import { apiClient } from "@/lib/apiClient";

export type LocationStatus = "ok" | "denied" | "unavailable" | "timeout" | "not_requested";

export type EventType =
  | "clock_in" | "clock_out" | "pause_start" | "pause_end" | "en_route" | "arrived" | "left_site" | "tracking"
  | "login" | "logout" | "connectivity_lost" | "connectivity_restored" | "location_denied" | "location_unavailable";

export interface AttendanceEventIn {
  event_type: EventType;
  client_event_id: string;
  device_at: string;
  latitude?: number | null;
  longitude?: number | null;
  accuracy_m?: number | null;
  location_status: LocationStatus;
  project_id?: string | null;
  note?: string | null;
}

export interface Shift {
  id: string;
  user_id: string;
  user_name: string | null;
  shift_date: string;
  starts_at: string;
  ends_at: string;
  break_minutes: number;
  scheduled_minutes: number;
  project_id: string | null;
  project_title: string | null;
  notes: string | null;
  status: string;
  compliance?: string;
  entry_id?: string | null;
}

export interface Entry {
  id: string;
  user_id: string;
  user_name?: string | null;
  shift_id: string | null;
  work_date: string;
  status: "open" | "closed" | "approved";
  clock_in_at: string;
  clock_in_offline: boolean;
  clock_out_at: string | null;
  clock_out_offline: boolean;
  closed_by: string | null;
  notes: string | null;
  elapsed_minutes: number;
  pause_minutes: number;
  effective_minutes: number;
  approved_minutes: number | null;
  paused: boolean;
  pauses: { started_at: string; ended_at: string | null; reason: string | null }[];
}

export interface ProjectOption {
  id: string;
  title: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
}

export interface Me {
  server_time: string;
  timezone: string;
  user: { id: string; full_name: string };
  shift: Shift | null;
  shift_status: string | null;
  late_minutes: number;
  shift_project: { id: string; title: string } | null;
  entry: Entry | null;
  must_clock_in: boolean;
  tracking_interval_minutes: number;
  location_retention_days: number;
  projects_today: ProjectOption[];
}

export interface ClockOutSummary {
  clock_in_at: string;
  clock_out_at: string;
  elapsed_minutes: number;
  pause_minutes: number;
  effective_minutes: number;
  pauses: number;
  shift: Shift | null;
  scheduled_minutes: number | null;
  difference_minutes: number | null;
  early_leave_minutes: number;
  projects: { id: string; title: string }[];
}

export const getMe = () => apiClient.get<Me>("/attendance/me").then((r) => r.data);
export const getClockOutSummary = () => apiClient.get<ClockOutSummary>("/attendance/me/summary").then((r) => r.data);
export const postEvent = (e: AttendanceEventIn) => apiClient.post("/attendance/events", e).then((r) => r.data);
export const postEventsBatch = (events: AttendanceEventIn[]) =>
  apiClient.post<{ results: { client_event_id: string; status: "ok" | "duplicate" | "error"; code?: string;
    message?: string }[] }>("/attendance/events/batch", { events }).then((r) => r.data.results);

// --- Malla -------------------------------------------------------------------

export interface Person { id: string; full_name: string; roles: string[] }

export const listPeople = () =>
  apiClient.get<Person[]>("/attendance/people", { params: { limit: 500 } }).then((r) => r.data);
export const listShifts = (date_from: string, date_to: string, user_id?: string) =>
  apiClient.get<Shift[]>("/attendance/shifts", { params: { date_from, date_to, user_id, limit: 500 } })
    .then((r) => r.data);
export const listMyShifts = (date_from: string, date_to: string) =>
  apiClient.get<Shift[]>("/attendance/me/shifts", { params: { date_from, date_to, limit: 500 } })
    .then((r) => r.data);
export interface ShiftsIn {
  user_ids: string[];
  date_from: string;
  date_to: string;
  weekdays?: number[];
  start_time: string;
  end_time: string;
  break_minutes: number;
  project_id?: string | null;
  notes?: string | null;
}
export const createShifts = (body: ShiftsIn) =>
  apiClient.post<{ created: Shift[]; skipped: { user_name: string; shift_date: string }[] }>(
    "/attendance/shifts", body).then((r) => r.data);
export const updateShift = (id: string, body: Partial<{ shift_date: string; start_time: string; end_time: string;
  break_minutes: number; project_id: string | null; notes: string | null }>) =>
  apiClient.patch<Shift>(`/attendance/shifts/${id}`, body).then((r) => r.data);
export const cancelShift = (id: string, reason?: string) =>
  apiClient.delete(`/attendance/shifts/${id}`, { params: { reason } });
export const copyWeek = (source_monday: string, target_monday: string) =>
  apiClient.post<{ created: number; skipped: number }>("/attendance/shifts/copy-week",
    { source_monday, target_monday }).then((r) => r.data);

// --- Configuración -------------------------------------------------------------

export interface AttendanceSettings {
  late_tolerance_minutes: number;
  early_leave_tolerance_minutes: number;
  daily_overtime_after_minutes: number;
  weekly_overtime_after_minutes: number;
  tracking_interval_minutes: number;
  location_retention_days: number;
  require_clock_in_for_field_work: boolean;
  paid_pauses: boolean;
}
export const getSettings = () => apiClient.get<AttendanceSettings>("/attendance/settings").then((r) => r.data);
export const putSettings = (s: Partial<AttendanceSettings>) =>
  apiClient.put<AttendanceSettings>("/attendance/settings", s).then((r) => r.data);

// --- Novedades y marcaciones ---------------------------------------------------

export const NOVELTY_KINDS: Record<string, string> = {
  late_arrival: "Llegada tarde",
  early_departure: "Salida anticipada",
  missed_clock_in: "Olvidé marcar la entrada",
  missed_clock_out: "Olvidé marcar la salida",
  correction: "Corregir una marcación",
  absence: "Ausencia",
  connectivity: "Sin señal o sin GPS",
  other: "Otra",
};

export interface Reason { id: string; code: string; name: string; active: boolean }
export interface Novelty {
  id: string;
  user_id: string;
  user_name: string | null;
  kind: string;
  kind_label: string;
  reason_name: string | null;
  work_date: string;
  description: string | null;
  time_entry_id: string | null;
  requested_clock_in_at: string | null;
  requested_clock_out_at: string | null;
  status: "pending" | "approved" | "rejected";
  reviewed_by_name: string | null;
  review_note: string | null;
  created_at: string | null;
}
export const listReasons = (include_inactive = false) =>
  apiClient.get<Reason[]>("/attendance/novelty-reasons", { params: { include_inactive } }).then((r) => r.data);
export const createReason = (name: string) =>
  apiClient.post<Reason>("/attendance/novelty-reasons", { name }).then((r) => r.data);
export const updateReason = (id: string, name: string, active: boolean) =>
  apiClient.put<Reason>(`/attendance/novelty-reasons/${id}`, { name, active }).then((r) => r.data);
export const createNovelty = (body: { kind: string; reason_id?: string | null; work_date?: string;
  description?: string; time_entry_id?: string | null; requested_clock_in_at?: string | null;
  requested_clock_out_at?: string | null }) =>
  apiClient.post<Novelty>("/attendance/novelties", body).then((r) => r.data);
export const listNovelties = (params: { status?: string; user_id?: string; date_from?: string; date_to?: string }) =>
  apiClient.get<Novelty[]>("/attendance/novelties", { params: { ...params, limit: 200 } }).then((r) => r.data);
export const reviewNovelty = (id: string, approve: boolean, note?: string) =>
  apiClient.post<Novelty>(`/attendance/novelties/${id}/${approve ? "approve" : "reject"}`, { note })
    .then((r) => r.data);

export const listEntries = (params: { date_from: string; date_to: string; user_id?: string; status?: string }) =>
  apiClient.get<Entry[]>("/attendance/entries", { params: { ...params, limit: 500 } }).then((r) => r.data);
export const listMyEntries = (date_from: string, date_to: string) =>
  apiClient.get<Entry[]>("/attendance/me/entries", { params: { date_from, date_to, limit: 200 } })
    .then((r) => r.data);
export interface EntryDetail extends Entry {
  events: { id: string; event_type: string; occurred_at: string; received_at: string; device_at: string | null;
    offline: boolean; location_status: string; latitude?: number | null; longitude?: number | null;
    accuracy_m?: number | null; distance_km: number | null; distance_source: string | null; note: string | null }[];
  corrections: { by: string; at: string; reason: string; before: Record<string, unknown>;
    after: Record<string, unknown> }[];
}
export const getEntry = (id: string) => apiClient.get<EntryDetail>(`/attendance/entries/${id}`).then((r) => r.data);
export const correctEntry = (id: string, body: { clock_in_at?: string | null; clock_out_at?: string | null;
  reason: string }) => apiClient.post<Entry>(`/attendance/entries/${id}/correct`, body).then((r) => r.data);
export const approveEntries = (entry_ids: string[]) =>
  apiClient.post<{ approved: string[]; errors: { entry_id: string; message: string }[] }>(
    "/attendance/entries/approve", { entry_ids }).then((r) => r.data);

// --- Panel y nómina -------------------------------------------------------------

export interface Dashboard {
  kpis: Record<string, number | null>;
  by_person: { user_id: string; user_name: string; scheduled_minutes: number; recorded_minutes: number;
    approved_minutes: number; shifts: number; late: number; compliance_pct: number | null }[];
  punctuality: { date: string; on_time: number; with_entry: number; pct: number | null }[];
  settings: { late_tolerance_minutes: number; early_leave_tolerance_minutes: number };
}
export interface LiveRow {
  user_id: string;
  user_name: string;
  shift: { starts_at: string; ends_at: string } | null;
  shift_status: string;
  entry_status: string | null;
  clock_in_at: string | null;
  clock_out_at: string | null;
  paused: boolean;
  offline: boolean;
  verified: boolean;
  location: { latitude: number; longitude: number; at: string; age_minutes: number; fresh: boolean;
    event_type: string } | null;
}
export const getDashboard = (date_from: string, date_to: string, user_id?: string) =>
  apiClient.get<Dashboard>("/attendance/dashboard", { params: { date_from, date_to, user_id } }).then((r) => r.data);
export const getLive = () => apiClient.get<LiveRow[]>("/attendance/live", { params: { limit: 500 } })
  .then((r) => r.data);

export interface PayrollRow {
  user_id: string;
  user_name: string;
  scheduled_minutes: number;
  recorded_minutes: number;
  pause_minutes: number;
  daily_overtime_minutes: number;
  weekly_overtime_minutes: number;
  approved_minutes: number;
  absences: number;
  late_arrivals: number;
  early_departures: number;
  open_entries: number;
  unapproved_entries: number;
  corrections: number;
  novelties: number;
}
export interface PayrollReport {
  date_from: string;
  date_to: string;
  period_status: string;
  rows: PayrollRow[];
  rules: { daily_overtime_after_minutes: number; weekly_overtime_after_minutes: number; paid_pauses: boolean };
}
export interface Period {
  id: string;
  start_date: string;
  end_date: string;
  status: "open" | "closed";
  closed_at: string | null;
  history: { action: string; by: string; at: string; reason: string | null }[];
}
export const getPayroll = (date_from: string, date_to: string) =>
  apiClient.get<PayrollReport>("/attendance/payroll/report", { params: { date_from, date_to } }).then((r) => r.data);
export const listPeriods = () => apiClient.get<Period[]>("/attendance/payroll/periods").then((r) => r.data);
export const createPeriod = (start_date: string, end_date: string) =>
  apiClient.post<Period>("/attendance/payroll/periods", { start_date, end_date }).then((r) => r.data);
export const setPeriodStatus = (id: string, close: boolean, reason?: string) =>
  apiClient.post<Period>(`/attendance/payroll/periods/${id}/${close ? "close" : "reopen"}`, { reason })
    .then((r) => r.data);

export async function downloadPayroll(kind: "xlsx" | "pdf", date_from: string, date_to: string) {
  const r = await apiClient.get(`/attendance/payroll/report.${kind}`, {
    params: { date_from, date_to }, responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `nomina-${date_from}-${date_to}.${kind}`;
  a.click();
  URL.revokeObjectURL(url);
}

// --- Mapa operativo -------------------------------------------------------------

export interface MapProject {
  id: string;
  title: string;
  customer_name: string;
  status: string;
  scheduled_date: string | null;
  technician_user_id: string | null;
  technician_name: string | null;
  address: string;
  latitude: number | null;
  longitude: number | null;
}
export interface MapPerson {
  user_id: string;
  user_name: string;
  latitude: number;
  longitude: number;
  accuracy_m: number | null;
  event_type: string;
  at: string;
  age_minutes: number;
  fresh: boolean;
  shift_open: boolean;
  project_id: string | null;
}
export interface MapRoute {
  user_id: string;
  date: string;
  origin: { latitude: number; longitude: number; at: string } | null;
  stops: (ProjectOption & { km_from_previous?: number })[];
  total_km: number;
  distance_source: string;
  directions_url: string | null;
}
export interface MiniMap {
  id: string;
  title: string;
  address: string;
  latitude: number | null;
  longitude: number | null;
  located: boolean;
  technician: { user_id: string; user_name: string | null; location: { latitude: number; longitude: number;
    at: string; age_minutes: number; fresh: boolean } | null } | null;
  straight_line_km: number | null;
  directions_url: string | null;
}

export const getMapProjects = (params: { status?: string; technician_user_id?: string; customer?: string;
  on_date?: string; ids?: string[] }) =>
  apiClient.get<{ projects: MapProject[]; unlocated: MapProject[] }>("/operations-map/projects", {
    params, paramsSerializer: { indexes: null } }).then((r) => r.data);
export const getMapPeople = () =>
  apiClient.get<MapPerson[]>("/operations-map/people", { params: { limit: 500 } }).then((r) => r.data);
export const getMapRoute = (on_date: string, user_id?: string) =>
  apiClient.get<MapRoute>("/operations-map/route", { params: { on_date, user_id } }).then((r) => r.data);
export const getMiniMap = (projectId: string) =>
  apiClient.get<MiniMap>(`/operations-map/projects/${projectId}`).then((r) => r.data);
export const setProjectLocation = (projectId: string, latitude: number, longitude: number) =>
  apiClient.put(`/operations-map/projects/${projectId}/location`, { latitude, longitude }).then((r) => r.data);

// --- Formato -------------------------------------------------------------------

export function hm(minutes: number | null | undefined): string {
  if (minutes == null) return "—";
  const signo = minutes < 0 ? "−" : "";
  const m = Math.abs(Math.round(minutes));
  return `${signo}${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")} min`;
}

export function clockTime(iso: string | null | undefined, timeZone?: string): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("es-US", { hour: "2-digit", minute: "2-digit", timeZone });
}

export function ageLabel(minutes: number): string {
  if (minutes < 1) return "ahora";
  if (minutes < 60) return `hace ${minutes} min`;
  if (minutes < 60 * 24) return `hace ${Math.floor(minutes / 60)} h`;
  return `hace ${Math.floor(minutes / (60 * 24))} d`;
}

export const SHIFT_STATUS_LABELS: Record<string, string> = {
  upcoming: "Por empezar",
  pending: "Pendiente de ingreso",
  in_progress: "En turno",
  completed: "Cumplido",
  late: "Llegó tarde",
  early_departure: "Salió antes",
  late_and_early: "Tarde y salió antes",
  incomplete: "Sin salida",
  missed: "Sin marcación",
  cancelled: "Cancelado",
  unscheduled: "Sin turno",
  unscheduled_open: "Marcó sin turno",
};
