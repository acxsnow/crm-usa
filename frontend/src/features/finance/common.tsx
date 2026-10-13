import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";

/** Selector de proyecto con búsqueda (el técnico solo ve los suyos: lo filtra el backend). */
export function ProjectPicker({ value, onChange, id, label = "Proyecto (opcional)" }: {
  value: string | null; onChange: (id: string | null) => void; id: string; label?: string;
}) {
  const [q, setQ] = useState("");
  const { data } = useQuery({
    queryKey: ["project-picker", q],
    queryFn: async () => (await apiClient.get<{ id: string; title: string }[]>("/projects", { params: { q: q || undefined, limit: 30 } })).data,
  });
  const opciones = data ?? [];
  return (
    <div className="form-field">
      <label className="form-label" htmlFor={id}>{label}</label>
      <div className="fin-picker">
        <input aria-label="Buscar proyecto" placeholder="Buscar…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value || null)}>
          <option value="">Sin proyecto</option>
          {opciones.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
          {value && !opciones.some((p) => p.id === value) && <option value={value}>(proyecto elegido)</option>}
        </select>
      </div>
    </div>
  );
}

/** Pestañas con el mismo estilo de Notificaciones. */
export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: [T, string][]; value: T; onChange: (t: T) => void }) {
  return (
    <div className="notices-tabs" role="tablist">
      {tabs.map(([k, l]) => (
        <button key={k} role="tab" type="button" aria-selected={value === k} className={value === k ? "is-on" : ""}
          onClick={() => onChange(k)}>{l}</button>
      ))}
    </div>
  );
}

export const fecha = (iso: string | null | undefined) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" }) : "—";
