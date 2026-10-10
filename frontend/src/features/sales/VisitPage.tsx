import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";

import "../billing/billing.css";
import "../programs/programs.css";
import "./sales.css";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { useGeolocation } from "@/lib/useGeolocation";
import { VISIT_RESULTS, myPrograms, recordVisit, salesKeys } from "./api";
import { useStates } from "@/features/programs/api";
import { CitySuggestions } from "@/components/CitySuggestions";

const MENSAJE: Record<string, string> = {
  created: "Visita registrada.",
  reopened: "Esta puerta ya tenía expediente: lo reabrimos.",
  updated: "Visita registrada en el expediente de esta puerta.",
  recorded: "Visita registrada en el expediente de esta puerta.",
  in_progress: "Esta puerta ya va más adelante en el proceso; solo se registró la visita.",
};

/**
 * Tocar una puerta (D6): dirección con el GPS del teléfono y el resultado en
 * botones grandes, para usar con una mano en el parque. Si abren, sigue
 * directo al formulario del programa.
 */
export function VisitPage() {
  const navigate = useNavigate();
  const geo = useGeolocation();
  const { data: mios } = useQuery({ queryKey: salesKeys.mine, queryFn: myPrograms });
  const [programa, setPrograma] = useState("");
  const [zona, setZona] = useState("");
  const [dir, setDir] = useState({ address_street: "", address_unit: "", address_city: "", address_state: "", address_zip: "" });
  const estados = useStates();
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [hecho, setHecho] = useState<string | null>(null);

  useEffect(() => { geo.request(); }, [geo.request]);
  useEffect(() => {
    if (mios?.length === 1 && !programa) {
      setPrograma(mios[0].program.id);
      if (mios[0].zones.length === 1) {
        setZona(mios[0].zones[0].id);
        setDir((d) => ({ ...d, address_city: d.address_city || mios[0].zones[0].city || "",
          address_state: d.address_state || mios[0].zones[0].state || "" }));
      }
    }
  }, [mios, programa]);
  const zonas = mios?.find((m) => m.program.id === programa)?.zones ?? [];

  const registrar = useMutation({
    mutationFn: (result: string) => recordVisit({
      ...dir, result, notes: notas || undefined, program_id: result === "opened" && programa ? programa : undefined,
      zone_id: result === "opened" && zona ? zona : undefined, ...(geo.coords ?? {}),
    }),
    onSuccess: (r, result) => {
      setError(null);
      if (result === "opened" && r.case.stage_code === "new_prospect") navigate(`/cases/${r.case.id}/form`);
      else {
        setHecho(MENSAJE[r.outcome] ?? "Visita registrada.");
        setDir((d) => ({ ...d, address_street: "", address_unit: "" }));
        setNotas("");
      }
    },
    onError: (e) => setError(apiErrorMessage(e)),
  });
  const listo = dir.address_street.trim().length > 0;

  return (
    <div className="sales-page">
      <Link to="/sales" className="acta-back"><span aria-hidden="true">‹</span> Mi día</Link>
      <article className="acta sales-visit">
        <header className="acta-header">
          <h1 className="acta-title">Tocar una puerta</h1>
          <p className={`sales-gps is-${geo.status}`}>
            {geo.status === "granted" && geo.coords ? `GPS listo · ${geo.coords.latitude.toFixed(4)}, ${geo.coords.longitude.toFixed(4)}`
              : geo.status === "requesting" ? "Buscando GPS…" : "Sin GPS: la visita se guarda sin ubicación"}
          </p>
        </header>
        {hecho && <p className="info-banner" role="status">{hecho} Puedes seguir con la siguiente puerta.</p>}
        {error && <p className="form-error" role="alert">{error}</p>}

        {(mios ?? []).length > 0 && (
          <div className="sales-fields">
            <div className="form-field"><label className="form-label" htmlFor="v-prog">Programa</label>
              <select id="v-prog" value={programa} onChange={(e) => { setPrograma(e.target.value); setZona(""); }}>
                <option value="">Lo elijo después</option>
                {(mios ?? []).map((m) => <option key={m.program.id} value={m.program.id}>{m.program.name}</option>)}
              </select></div>
            {zonas.length > 0 && (
              <div className="form-field"><label className="form-label" htmlFor="v-zona">Parque o zona</label>
                <select id="v-zona" value={zona} onChange={(e) => {
                  setZona(e.target.value);
                  const z = zonas.find((x) => x.id === e.target.value);
                  if (z) setDir((d) => ({ ...d, address_city: z.city ?? d.address_city, address_state: z.state ?? d.address_state }));
                }}>
                  <option value="">Elige…</option>
                  {zonas.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
                </select></div>
            )}
          </div>
        )}

        <div className="sales-fields">
          <div className="form-field is-wide"><label className="form-label" htmlFor="v-calle">Dirección <span className="form-req">*</span></label>
            <input id="v-calle" autoComplete="street-address" value={dir.address_street} placeholder="1200 W Sunrise Dr"
              onChange={(e) => setDir({ ...dir, address_street: e.target.value })} /></div>
          <div className="form-field"><label className="form-label" htmlFor="v-unidad">Espacio o unidad</label>
            <input id="v-unidad" value={dir.address_unit} placeholder="Spc 14" onChange={(e) => setDir({ ...dir, address_unit: e.target.value })} /></div>
          {/* El estado va primero: las ciudades sugeridas dependen de él. */}
          <div className="form-field"><label className="form-label" htmlFor="v-estado">Estado</label>
            <select id="v-estado" value={dir.address_state} onChange={(e) => setDir({ ...dir, address_state: e.target.value })}>
              <option value="">—</option>
              {estados.map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select></div>
          <div className="form-field"><label className="form-label" htmlFor="v-ciudad">Ciudad</label>
            <input id="v-ciudad" list="v-ciudad-options" value={dir.address_city} onChange={(e) => setDir({ ...dir, address_city: e.target.value })} />
            <CitySuggestions id="v-ciudad-options" state={dir.address_state || undefined} value={dir.address_city} /></div>
          <div className="form-field"><label className="form-label" htmlFor="v-zip">ZIP</label>
            <input id="v-zip" inputMode="numeric" value={dir.address_zip} onChange={(e) => setDir({ ...dir, address_zip: e.target.value })} /></div>
          <div className="form-field is-wide"><label className="form-label" htmlFor="v-notas">Notas (opcional)</label>
            <input id="v-notas" value={notas} placeholder="Perro en el patio, volver después de las 5" onChange={(e) => setNotas(e.target.value)} /></div>
        </div>

        <h2 className="sales-question">¿Qué pasó en la puerta?</h2>
        <div className="sales-results">
          {VISIT_RESULTS.map((r) => (
            <button key={r.value} type="button" className={`sales-result is-${r.value}`} disabled={!listo || registrar.isPending}
              onClick={() => registrar.mutate(r.value)}>
              <strong>{r.label}</strong>{r.hint && <small>{r.hint}</small>}
            </button>
          ))}
        </div>
        {!listo && <p className="acta-empty">Escribe la dirección para registrar la visita.</p>}
      </article>
    </div>
  );
}
