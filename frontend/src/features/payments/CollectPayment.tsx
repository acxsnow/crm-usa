import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import QRCode from "qrcode";
import { toast } from "@/lib/toast";
import { createPaymentLink, getPaymentsStatus, listPaymentLinks, revokePaymentLink, usd, type PaymentLink } from "./api";
import "./payments.css";

const ESTADO: Record<string, string> = {
  active: "Enviado", processing: "Pago del banco en camino", paid: "Pagado", failed: "Falló", revoked: "Reemplazado",
};

function apiError(e: unknown): string {
  return (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail ?? "No se pudo crear el cobro.";
}

/**
 * «Cobrar» de una factura, como en Housecall Pro: se elige cuánto (el saldo,
 * un anticipo del 50 % u otro monto) y cómo (correo, SMS o QR en la obra). El
 * cliente paga con tarjeta o desde su banco y el pago entra solo.
 */
export function CollectPayment({ invoiceId, balance, onPaid }: { invoiceId: string; balance: number; onPaid?: () => void }) {
  const qc = useQueryClient();
  const { data: estado } = useQuery({ queryKey: ["payments-status"], queryFn: getPaymentsStatus, staleTime: 300_000 });
  const { data: enlaces } = useQuery({ queryKey: ["payment-links", invoiceId], queryFn: () => listPaymentLinks(invoiceId),
    refetchInterval: 15_000 });
  const [abierto, setAbierto] = useState(false);
  const [modo, setModo] = useState<"full" | "half" | "other">("full");
  const [otro, setOtro] = useState("");
  const [email, setEmail] = useState(true);
  const [sms, setSms] = useState(false);
  const [creado, setCreado] = useState<PaymentLink | null>(null);
  const [qr, setQr] = useState<string | null>(null);

  const ultimo = enlaces?.[0];
  useEffect(() => {
    if (ultimo?.status === "paid") onPaid?.();
  }, [ultimo?.status, onPaid]);

  const monto = modo === "full" ? balance : modo === "half" ? Math.round(balance * 50) / 100 : Number(otro || 0);
  const crear = useMutation({
    mutationFn: (como: "send" | "qr") => createPaymentLink(invoiceId, {
      kind: modo === "full" ? "full" : "deposit", amount: modo === "full" ? undefined : monto.toFixed(2),
      send_email: como === "send" && email, send_sms: como === "send" && sms }),
    onSuccess: async (link, como) => {
      setCreado(link);
      setQr(como === "qr" && link.url ? await QRCode.toDataURL(link.url, { margin: 1, width: 320 }) : null);
      toast(como === "send" ? "Cobro enviado al cliente" : "Enlace listo: muéstrale el código al cliente");
      qc.invalidateQueries({ queryKey: ["payment-links", invoiceId] });
    },
    onError: (e) => toast(apiError(e)),
  });
  const anular = useMutation({
    mutationFn: (id: string) => revokePaymentLink(id),
    onSuccess: () => { toast("Enlace anulado"); qc.invalidateQueries({ queryKey: ["payment-links", invoiceId] }); },
  });

  if (estado && !estado.online_payments) {
    return <p className="pay-note">El cobro en línea se activa cuando se configure la cuenta de Stripe de la empresa.</p>;
  }

  return (
    <section className="pay-collect" aria-label="Cobrar en línea">
      {!abierto ? (
        <button type="button" className="primary-button pay-cta" onClick={() => setAbierto(true)}>
          Cobrar {usd(balance)}
        </button>
      ) : (
        <div className="pay-box">
          <div className="pay-box-head">
            <strong>Cobrar en línea</strong>
            <button type="button" className="link-button" onClick={() => { setAbierto(false); setCreado(null); setQr(null); }}>Cerrar</button>
          </div>
          <fieldset className="pay-amounts">
            <legend>¿Cuánto?</legend>
            <label className={modo === "full" ? "is-on" : ""}><input type="radio" name={`m-${invoiceId}`} checked={modo === "full"}
              onChange={() => setModo("full")} /> Saldo <b>{usd(balance)}</b></label>
            <label className={modo === "half" ? "is-on" : ""}><input type="radio" name={`m-${invoiceId}`} checked={modo === "half"}
              onChange={() => setModo("half")} /> Anticipo 50 % <b>{usd(balance / 2)}</b></label>
            <label className={modo === "other" ? "is-on" : ""}><input type="radio" name={`m-${invoiceId}`} checked={modo === "other"}
              onChange={() => setModo("other")} /> Otro monto
              {modo === "other" && <input type="number" min="1" step="0.01" max={balance} value={otro} aria-label="Monto"
                onChange={(e) => setOtro(e.target.value)} placeholder="0.00" />}</label>
          </fieldset>
          <div className="pay-send">
            <label><input type="checkbox" checked={email} onChange={(e) => setEmail(e.target.checked)} /> Correo</label>
            <label><input type="checkbox" checked={sms} onChange={(e) => setSms(e.target.checked)} /> SMS</label>
          </div>
          <div className="pay-actions">
            <button type="button" className="primary-button" disabled={crear.isPending || monto <= 0 || (!email && !sms)}
              onClick={() => crear.mutate("send")}>Enviar enlace de pago</button>
            <button type="button" className="acta-btn" disabled={crear.isPending || monto <= 0}
              onClick={() => crear.mutate("qr")}>Cobrar aquí con QR</button>
          </div>
          <p className="pay-note">El cliente paga con tarjeta, Apple Pay o Google Pay, o desde su cuenta bancaria (ACH).
            El pago entra solo a la factura.</p>
          {creado?.url && (
            <div className="pay-result">
              {qr && <img src={qr} alt="Código QR para pagar la factura" width={200} height={200} />}
              <div className="pay-url">
                <input readOnly value={creado.url} aria-label="Enlace de pago" onFocus={(e) => e.currentTarget.select()} />
                <button type="button" className="acta-btn" onClick={async () => {
                  try { await navigator.clipboard.writeText(creado.url!); toast("Enlace copiado"); } catch { toast("Selecciona el enlace y cópialo"); }
                }}>Copiar</button>
              </div>
            </div>
          )}
        </div>
      )}
      {!!enlaces?.length && (
        <ul className="pay-links">
          {enlaces.slice(0, 5).map((l) => (
            <li key={l.id}>
              <span className={`status-pill pay-${l.status}`}>{ESTADO[l.status] ?? l.status}</span>
              <span>{l.kind === "deposit" ? `Anticipo ${usd(l.amount)}` : `Saldo ${usd(l.amount_due)}`}</span>
              <span className="pay-muted">{[l.sent_to_email, l.sent_to_phone].filter(Boolean).join(" · ") || "QR o enlace"}
                {l.opened_at ? " · lo abrió" : ""}</span>
              {l.status === "active" && <button type="button" className="link-button" onClick={() => anular.mutate(l.id)}>Anular</button>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
