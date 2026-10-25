import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "@/lib/toast";
import { createNovelty, listReasons, NOVELTY_KINDS } from "./api";

/** Hora local `HH:MM` de hoy (o de `dia`) como ISO, para pedir una corrección. */
function aIso(dia: string, hora: string): string | null {
  if (!hora) return null;
  return new Date(`${dia}T${hora}:00`).toISOString();
}

/**
 * Registrar una novedad: lo que el empleado declara (llegué tarde por X,
 * olvidé marcar). No cambia nada por sí sola: Administración la aprueba o la
 * rechaza, y solo una corrección aprobada cambia las horas.
 */
export function NoveltyForm({ entryId, defaultKind = "other", onDone, onCancel }: {
  entryId?: string | null;
  defaultKind?: string;
  onDone?: () => void;
  onCancel?: () => void;
}) {
  const qc = useQueryClient();
  const hoy = new Date().toLocaleDateString("en-CA");
  const [kind, setKind] = useState(defaultKind);
  const [reasonId, setReasonId] = useState("");
  const [dia, setDia] = useState(hoy);
  const [entrada, setEntrada] = useState("");
  const [salida, setSalida] = useState("");
  const [texto, setTexto] = useState("");
  const { data: motivos } = useQuery({ queryKey: ["novelty-reasons"], queryFn: () => listReasons() });
  const pideHoras = ["missed_clock_in", "missed_clock_out", "correction"].includes(kind);

  const guardar = useMutation({
    mutationFn: () => createNovelty({
      kind, reason_id: reasonId || null, work_date: dia, description: texto || undefined,
      time_entry_id: entryId ?? null, requested_clock_in_at: aIso(dia, entrada),
      requested_clock_out_at: aIso(dia, salida),
    }),
    onSuccess: () => {
      toast("Novedad enviada a Administración");
      qc.invalidateQueries({ queryKey: ["my-novelties"] });
      onDone?.();
    },
  });

  return (
    <form className="att-form" onSubmit={(e) => { e.preventDefault(); guardar.mutate(); }}>
      <label>Qué pasó
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          {Object.entries(NOVELTY_KINDS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>
      </label>
      <label>Motivo
        <select value={reasonId} onChange={(e) => setReasonId(e.target.value)}>
          <option value="">Elige un motivo</option>
          {(motivos ?? []).map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
        </select>
      </label>
      <label>Día
        <input type="date" value={dia} max={hoy} onChange={(e) => setDia(e.target.value)} />
      </label>
      {pideHoras && (
        <div className="att-form-row">
          {kind !== "missed_clock_out" && (
            <label>Hora de entrada real
              <input type="time" value={entrada} onChange={(e) => setEntrada(e.target.value)} />
            </label>
          )}
          {/* Para la entrada olvidada también: la marcación que se crea necesita las dos horas. */}
          <label>Hora de salida real
            <input type="time" value={salida} onChange={(e) => setSalida(e.target.value)} />
          </label>
        </div>
      )}
      <label>Observaciones
        <textarea value={texto} maxLength={2000} onChange={(e) => setTexto(e.target.value)}
          placeholder="Cuenta brevemente qué pasó" />
      </label>
      {guardar.isError && <p className="att-error" role="alert">
        {(guardar.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
          ?? "No se pudo enviar la novedad."}</p>}
      <div className="att-actions">
        {onCancel && <button type="button" className="att-btn" onClick={onCancel}>Cancelar</button>}
        <button type="submit" className="att-btn is-primary" disabled={guardar.isPending}>
          {guardar.isPending ? "Enviando…" : "Enviar novedad"}
        </button>
      </div>
    </form>
  );
}
