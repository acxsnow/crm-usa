import { useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getPublicInvoice, startCheckout, usd } from "./api";
import "./payments.css";

function fecha(iso: string | null): string {
  return iso ? new Date(`${iso}T12:00:00`).toLocaleDateString("es-US", { day: "numeric", month: "long", year: "numeric" }) : "—";
}

/**
 * La factura en línea que recibe el cliente (como «View & Pay» de Housecall
 * Pro): sin sesión, solo su factura. Pagar abre la página segura de Stripe;
 * aquí nunca se escribe una tarjeta.
 */
export function PayInvoicePage() {
  const { token = "" } = useParams();
  const [params] = useSearchParams();
  const recienPagado = params.get("pagado") === "1";
  const [error, setError] = useState<string | null>(null);
  const [yendo, setYendo] = useState(false);
  const { data, isLoading, isError } = useQuery({ queryKey: ["public-invoice", token], queryFn: () => getPublicInvoice(token),
    retry: false, refetchInterval: recienPagado ? 4000 : false });

  const pagar = async () => {
    setYendo(true);
    setError(null);
    try {
      const { url } = await startCheckout(token);
      window.location.assign(url);
    } catch (e) {
      setError((e as { response?: { data?: { detail?: string } } })?.response?.data?.detail
        ?? "No se pudo abrir el pago. Inténtalo de nuevo.");
      setYendo(false);
    }
  };

  if (isLoading) return <main className="payp"><div className="payp-card"><p>Cargando tu factura…</p></div></main>;
  if (isError || !data) {
    return (
      <main className="payp"><div className="payp-card">
        <h1>Enlace no válido</h1>
        <p className="payp-muted">Este enlace ya no sirve. Pide uno nuevo a la empresa que te atendió.</p>
      </div></main>
    );
  }

  const pagada = data.status === "paid";
  return (
    <main className="payp">
      <div className="payp-card">
        <header className="payp-head">
          <span className="payp-logo" aria-hidden="true">{data.company.charAt(0)}</span>
          <div><strong>{data.company}</strong><span className="payp-muted">Factura {data.invoice_number}</span></div>
        </header>

        {pagada || recienPagado ? (
          <div className="payp-done" role="status">
            <span aria-hidden="true">✓</span>
            <h1>{pagada ? "Factura pagada" : "Recibimos tu pago"}</h1>
            <p className="payp-muted">{pagada ? "Gracias. No tienes saldo pendiente con esta factura."
              : "Estamos confirmando el pago. Si pagaste desde tu banco, puede tardar de 2 a 4 días hábiles."}</p>
          </div>
        ) : (
          <>
            <p className="payp-muted">Hola {data.customer_name},</p>
            <div className="payp-amount">
              <span>{data.kind === "deposit" ? "Anticipo a pagar" : "Total a pagar"}</span>
              <strong>{usd(data.amount_requested)}</strong>
              {data.due_date && <span className="payp-muted">Vence el {fecha(data.due_date)}</span>}
            </div>
            {data.status === "processing" && (
              <p className="payp-info">Ya hay un pago desde tu banco en camino. Te avisaremos cuando se confirme.</p>
            )}
            {data.online_enabled && data.status === "open" ? (
              <button type="button" className="payp-pay" onClick={pagar} disabled={yendo}>
                {yendo ? "Abriendo pago seguro…" : `Pagar ${usd(data.amount_requested)}`}
              </button>
            ) : data.status === "open" && <p className="payp-info">El pago en línea no está disponible ahora. Comunícate con la empresa.</p>}
            {error && <p className="payp-error" role="alert">{error}</p>}
            <p className="payp-methods">Tarjeta de crédito o débito, Apple Pay, Google Pay o tu cuenta bancaria.
              El pago lo procesa Stripe; la empresa no ve los datos de tu tarjeta.</p>
          </>
        )}

        <section className="payp-detail" aria-label="Detalle de la factura">
          <h2>Detalle</h2>
          <ul>
            {data.lines.map((l, i) => (
              <li key={i} className={l.kind === "rebate" ? "is-rebate" : ""}>
                <span>{l.description}{Number(l.quantity) !== 1 ? ` × ${Number(l.quantity)}` : ""}</span>
                <span>{l.kind === "rebate" ? "−" : ""}{usd(l.amount)}</span>
              </li>
            ))}
          </ul>
          <dl>
            {Number(data.rebates) > 0 && <div><dt>Incentivos</dt><dd>−{usd(data.rebates)}</dd></div>}
            <div><dt>Total</dt><dd>{usd(data.total)}</dd></div>
            {Number(data.paid) > 0 && <div><dt>Pagado</dt><dd>−{usd(data.paid)}</dd></div>}
            <div className="is-balance"><dt>Saldo</dt><dd>{usd(data.balance)}</dd></div>
          </dl>
          <p className="payp-muted">Emitida el {fecha(data.issue_date)}</p>
        </section>
      </div>
    </main>
  );
}
