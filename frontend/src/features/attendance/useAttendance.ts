import { useCallback, useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthContext";
import { toast } from "@/lib/toast";
import { getMe, type EventType } from "./api";
import { flush, mark, subscribeQueue, type SendResult } from "./offlineQueue";

export const ME_KEY = ["attendance-me"];

/** El estado del turno propio. Solo para quien marca (`attendance.clock`). */
export function useMyAttendance() {
  const { hasPermission } = useAuth();
  const puede = hasPermission("attendance.clock");
  return useQuery({ queryKey: ME_KEY, queryFn: getMe, enabled: puede, refetchInterval: 60_000,
    retry: false, staleTime: 15_000 });
}

/** Marcas sin enviar, para la franja «3 marcas sin enviar». */
export function usePendingMarks(): number {
  const [n, setN] = useState(0);
  useEffect(() => subscribeQueue(setN), []);
  return n;
}

const OK_MSG: Partial<Record<EventType, string>> = {
  clock_in: "Turno iniciado",
  clock_out: "Turno finalizado",
  pause_start: "Pausa iniciada",
  pause_end: "Turno reanudado",
  en_route: "En camino registrado",
  arrived: "Llegada registrada",
  left_site: "Salida de obra registrada",
};

/** Marca un evento (con ubicación si se puede) y avisa qué pasó, sin perder
 * la marca si no hay señal. */
export function useMark() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState<EventType | null>(null);
  const run = useCallback(async (tipo: EventType, extra: { project_id?: string | null; note?: string | null;
    withLocation?: boolean } = {}): Promise<SendResult> => {
    setBusy(tipo);
    try {
      const r = await mark(tipo, extra);
      if (r.offline) toast("Sin señal: la marca quedó guardada y se enviará sola");
      else if (r.errors.length) toast(r.errors[r.errors.length - 1].message);
      else if (OK_MSG[tipo]) toast(OK_MSG[tipo]!);
      await qc.invalidateQueries({ queryKey: ME_KEY });
      return r;
    } finally {
      setBusy(null);
    }
  }, [qc]);
  return { run, busy };
}

export async function flushQueue() {
  return flush();
}
