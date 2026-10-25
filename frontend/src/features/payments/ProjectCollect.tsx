import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/features/auth/AuthContext";
import { CollectPayment } from "./CollectPayment";
import { listProjectOpenInvoices, usd } from "./api";

/**
 * Cobrar en la obra (como el técnico en Housecall Pro): las facturas del
 * trabajo particular de esta obra que tienen saldo, cada una con su «Cobrar».
 */
export function ProjectCollect({ projectId }: { projectId: string }) {
  const { hasPermission } = useAuth();
  const puede = hasPermission("payments.collect");
  const { data, refetch } = useQuery({ queryKey: ["project-open-invoices", projectId],
    queryFn: () => listProjectOpenInvoices(projectId), enabled: puede });
  if (!puede || !data?.length) return null;
  return (
    <section className="annex-section" aria-labelledby="anexo-cobro">
      <div className="annex-section-head"><h3 id="anexo-cobro">Cobrar al cliente</h3></div>
      <p className="acta-lead">El cliente paga con tarjeta o desde su banco, por enlace o con el código QR en tu celular.</p>
      {data.map((f) => (
        <div key={f.id} className="pay-project-invoice">
          <p><strong>Factura {f.invoice_number}</strong> · total {usd(f.total)} · saldo {usd(f.balance)}</p>
          <CollectPayment invoiceId={f.id} balance={Number(f.balance)} onPaid={() => { void refetch(); }} />
        </div>
      ))}
    </section>
  );
}
