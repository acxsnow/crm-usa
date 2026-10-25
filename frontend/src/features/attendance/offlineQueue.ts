/**
 * Cola de marcas sin señal.
 *
 * Toda marca nace aquí con su id (`client_event_id`) y la hora del teléfono, se
 * guarda en el almacenamiento local y se intenta enviar de una. Si no hay
 * señal, queda guardada y se reintenta al volver la red, cada 30 segundos y al
 * abrir la app. El servidor usa el id para no duplicar: reenviar la misma marca
 * dos veces es seguro (spec, «Geolocalización y sin señal»).
 *
 * La cola es por persona: si alguien más inicia sesión en el mismo teléfono,
 * no envía marcas ajenas.
 */
import axios from "axios";
import { postEventsBatch, type AttendanceEventIn, type EventType, type LocationStatus } from "./api";

const PREFIX = "crm.attendance.queue.";
type Listener = (pending: number) => void;
const listeners = new Set<Listener>();
let userId: string | null = null;
let sending: Promise<SendResult> | null = null;

export interface SendResult {
  sent: number;
  errors: { client_event_id: string; message: string; code?: string }[];
  offline: boolean;
}

function key(): string | null {
  return userId ? PREFIX + userId : null;
}

function read(): AttendanceEventIn[] {
  const k = key();
  if (!k) return [];
  try {
    const raw = localStorage.getItem(k);
    return raw ? (JSON.parse(raw) as AttendanceEventIn[]) : [];
  } catch {
    return [];
  }
}

function write(items: AttendanceEventIn[]) {
  const k = key();
  if (!k) return;
  try {
    if (items.length) localStorage.setItem(k, JSON.stringify(items.slice(-500)));
    else localStorage.removeItem(k);
  } catch {
    /* almacenamiento lleno o bloqueado: la marca se intenta enviar igual */
  }
  listeners.forEach((l) => l(items.length));
}

export function setQueueUser(id: string | null) {
  userId = id;
  listeners.forEach((l) => l(read().length));
}

export function pendingCount(): number {
  return read().length;
}

export function subscribeQueue(l: Listener): () => void {
  listeners.add(l);
  l(read().length);
  return () => { listeners.delete(l); };
}

function newId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

/** Posición actual, sin inventar: si no hay permiso o GPS, lo dice. */
export function currentPosition(timeoutMs = 15000): Promise<{
  latitude?: number; longitude?: number; accuracy_m?: number; location_status: LocationStatus }> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) {
      resolve({ location_status: "unavailable" });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => resolve({ latitude: p.coords.latitude, longitude: p.coords.longitude,
        accuracy_m: Math.round(p.coords.accuracy), location_status: "ok" }),
      (err) => resolve({ location_status: err.code === err.PERMISSION_DENIED ? "denied"
        : err.code === err.TIMEOUT ? "timeout" : "unavailable" }),
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60_000 },
    );
  });
}

/** Encola una marca y trata de enviarla. */
export async function mark(event_type: EventType, extra: {
  project_id?: string | null; note?: string | null; withLocation?: boolean } = {}): Promise<SendResult> {
  const pos = extra.withLocation === false ? { location_status: "not_requested" as const }
    : await currentPosition();
  const evento: AttendanceEventIn = {
    event_type, client_event_id: newId(), device_at: new Date().toISOString(), ...pos,
    project_id: extra.project_id ?? null, note: extra.note ?? null,
  };
  write([...read(), evento]);
  return flush();
}

/** Envía lo pendiente, en orden. Lo que el servidor aceptó o ya tenía sale de
 * la cola; lo que rechazó por una regla (p. ej. «ya tienes un turno») también
 * sale, y se informa; lo que no llegó por red se queda. */
export function flush(): Promise<SendResult> {
  if (sending) return sending;
  sending = (async (): Promise<SendResult> => {
    const items = read();
    if (!items.length) return { sent: 0, errors: [], offline: false };
    try {
      const resultados = await postEventsBatch(items);
      const errores = resultados.filter((r) => r.status === "error")
        .map((r) => ({ client_event_id: r.client_event_id, message: r.message ?? "No se pudo registrar.",
          code: r.code }));
      const vistos = new Set(resultados.map((r) => r.client_event_id));
      write(read().filter((e) => !vistos.has(e.client_event_id)));
      return { sent: resultados.length - errores.length, errors: errores, offline: false };
    } catch (err) {
      // Sin red (o el servidor caído): todo se queda para el próximo intento.
      const sinRed = !axios.isAxiosError(err) || !err.response || err.response.status >= 500;
      if (!sinRed) {
        // 4xx del lote completo (p. ej. sesión vencida): se conserva para reintentar tras iniciar sesión.
        return { sent: 0, errors: [], offline: false };
      }
      return { sent: 0, errors: [], offline: true };
    }
  })().finally(() => { sending = null; });
  return sending;
}
