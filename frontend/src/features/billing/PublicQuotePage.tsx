import { useState } from "react";
import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { SignaturePad } from "@/features/field-ops/SignaturePad";
import "@/features/payments/payments.css";
import { acceptPublicQuote, getPublicQuote, rejectPublicQuote } from "./billingApi";

const usd = (v: string | number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(Number(v));
const fecha = (iso: string | null) =>
  iso ? new Date(iso.length === 10 ? `${iso}T12:00:00` : iso).toLocaleDateString("es-US", { day: "numeric", month: "long", year: "numeric" }) : "—";

/**
 * La cotización que recibe el cliente (como en Housecall Pro): sin sesión, la
 * ve, elige la opción, firma y acepta, o la rechaza con un motivo.
 */
export function PublicQuotePage() {
  const { token = "" } = useParams();
  const qc = useQueryClient();
  const { data: q, isLoading, isError } = useQuery({ queryKey: ["public-quote", token], queryFn: () => getPublicQuote(token), retry: false });
  const [opcion, setOpcion] = useState<string | null>(null);
  const [nombre, setNombre] = useState("");
  const [firma, setFirma] = useState<string | null>(null);
  const [rechazando, setRechazando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const listo = { onSuccess: () => { setError(null); return qc.invalidateQueries({ queryKey: ["public-quote", token] }); },
    onError: (e: unknown) => setError(apiErrorMessage(e)) };
  const aceptar = useMutation({ mutationFn: () => acceptPublicQuote(token, { option: opcion, signer_name: nombre.trim(), signature_base64: firma! }), ...listo });
  const rechazar = useMutation({ mutationFn: () => rejectPublicQuote(token, motivo.trim()), ...listo });

  if (isLoading) return <main className="payp"><div className="payp-card"><p>Cargando tu cotización…</p></div></main>;
  if (isError || !q) {
    return (
      <main className="payp"><div className="payp-card">
        <h1>Enlace no válido</h1>
        <p className="payp-muted">Este enlace ya no sirve. Pide uno nuevo a la empresa que te atendió.</p>
      </div></main>
    );
  }

  const conOpciones = q.options.length > 0;
  const visible = q.accepted_option ?? opcion;
  const lineas = q.lines.filter((l) => !l.option_key || !conOpciones || l.option_key === visible);
  const total = conOpciones ? q.options.find((o) => o.key === visible)?.total ?? null : q.total;
  const puedeAceptar = (!conOpciones || !!opcion) && nombre.trim().length >= 3 && !!firma && !aceptar.isPending;

  return (
    <main className="payp">
      <div className="payp-card">
        <header className="payp-head">
          <span className="payp-logo" aria-hidden="true">{(q.company || "P").charAt(0)}</span>
          <div><strong>{q.company}</strong><span className="payp-muted">Cotización {q.quote_number} · para {q.customer_name}</span></div>
        </header>
        <h1>{q.title ?? "Tu cotización"}</h1>

        {q.status === "accepted" && <div className="payp-done"><span aria-hidden="true">✓</span><strong>Cotización aceptada</strong>
          <p className="payp-muted">Firmó {q.signer_name ?? "la empresa"} el {fecha(q.decided_at)}. Te contactaremos para agendar el trabajo.</p></div>}
        {q.status === "rejected" && <p className="payp-info">No aceptaste esta cotización. La empresa ya lo sabe y puede enviarte otra.</p>}
        {q.status === "expired" && <p className="payp-info">Esta cotización venció el {fecha(q.valid_until)}. Pide una nueva a la empresa.</p>}

        {conOpciones && (
          <fieldset className="pay-amounts">
            <legend>{q.can_decide ? "Elige una opción" : "Opciones"}</legend>
            {q.options.map((o) => (
              <label key={o.key} className={visible === o.key ? "is-on" : undefined}>
                <input type="radio" name="opcion" value={o.key} checked={visible === o.key} disabled={!q.can_decide}
                  onChange={() => setOpcion(o.key)} />
                {o.label}<b>{usd(o.total)}</b>
              </label>
            ))}
          </fieldset>
        )}

        {(!conOpciones || visible) && (
          <section className="payp-detail">
            <h2>Detalle</h2>
            <ul>
              {lineas.map((l, i) => (
                <li key={i}><span>{l.description}{Number(l.quantity) !== 1 ? ` × ${Number(l.quantity)}` : ""}</span><span>{usd(l.amount)}</span></li>
              ))}
            </ul>
            {total !== null && <dl><div className="is-balance"><dt>Total</dt><dd>{usd(total)}</dd></div></dl>}
          </section>
        )}
        {q.notes && <p className="payp-muted">{q.notes}</p>}
        {q.valid_until && q.can_decide && <p className="payp-muted">Vigente hasta el {fecha(q.valid_until)}.</p>}
        {error && <p className="payp-error" role="alert">{error}</p>}

        {q.can_decide && !rechazando && (
          <>
            <label className="signature-label">Tu nombre completo
              <input value={nombre} maxLength={255} autoComplete="name" onChange={(e) => setNombre(e.target.value)} />
            </label>
            <p className="signature-label">Firma dentro del recuadro</p>
            <SignaturePad hideCapture onCapture={setFirma} onDraw={setFirma} />
            <button type="button" className="payp-pay" disabled={!puedeAceptar} onClick={() => aceptar.mutate()}>
              {aceptar.isPending ? "Guardando…" : "Aceptar y firmar"}</button>
            <button type="button" className="link-button" onClick={() => setRechazando(true)}>No me interesa</button>
          </>
        )}
        {q.can_decide && rechazando && (
          <form onSubmit={(e) => { e.preventDefault(); rechazar.mutate(); }}>
            <label className="signature-label">Cuéntanos por qué
              <textarea required minLength={3} maxLength={2000} value={motivo} onChange={(e) => setMotivo(e.target.value)} />
            </label>
            <button type="submit" className="payp-pay" disabled={rechazar.isPending}>Enviar respuesta</button>
            <button type="button" className="link-button" onClick={() => setRechazando(false)}>Volver</button>
          </form>
        )}
      </div>
    </main>
  );
}
