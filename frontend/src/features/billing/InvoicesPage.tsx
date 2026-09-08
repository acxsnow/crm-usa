import { Fragment, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createInvoice,
  downloadInvoicesCsv,
  fetchInvoiceAttachmentObjectUrl,
  getFinanceDashboard,
  listInvoicesPage,
  markInvoiceSent,
  recordInvoicePayment,
  uploadInvoiceAttachment,
} from "./api";
import { listProjects } from "@/features/field-ops/api";
import { PaginationControls } from "@/components/PaginationControls";
import type { Invoice } from "@/types/billing";

const PAGE_SIZE = 20;

function AttachmentsList({ invoice }: { invoice: Invoice }) {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const uploadMutation = useMutation({
    mutationFn: (file: File) => uploadInvoiceAttachment(invoice.id, file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const handleView = async (attachmentId: string) => {
    const url = await fetchInvoiceAttachmentObjectUrl(attachmentId);
    window.open(url, "_blank");
  };

  return (
    <div className="attachments-block" style={{ margin: "0.35rem 0" }}>
      <strong style={{ fontSize: "0.85rem" }}>Comprobantes / documentos:</strong>{" "}
      {invoice.attachments.length === 0 && <span className="page-subtitle">Sin adjuntos aún.</span>}
      {invoice.attachments.map((att) => (
        <button
          key={att.id}
          type="button"
          className="link-button"
          style={{ marginRight: "0.5rem" }}
          onClick={() => handleView(att.id)}
        >
          {att.original_filename ?? "archivo"}
        </button>
      ))}
      <div className="inline-form" style={{ marginTop: "0.25rem" }}>
        <input
          ref={fileInputRef}
          type="file"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) uploadMutation.mutate(file);
          }}
        />
        {uploadMutation.isPending && <span className="page-subtitle">Subiendo...</span>}
      </div>
    </div>
  );
}

function PaymentForm({ invoiceId }: { invoiceId: string }) {
  const queryClient = useQueryClient();
  const [amount, setAmount] = useState("");
  const [paidAt, setPaidAt] = useState(new Date().toISOString().slice(0, 10));

  const mutation = useMutation({
    mutationFn: () => recordInvoicePayment(invoiceId, { amount: Number(amount), paid_at: paidAt }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      setAmount("");
    },
  });

  return (
    <form
      className="inline-form"
      style={{ margin: "0.35rem 0" }}
      onSubmit={(e) => {
        e.preventDefault();
        if (amount) mutation.mutate();
      }}
    >
      <input type="number" step="0.01" placeholder="Monto pagado" value={amount} onChange={(e) => setAmount(e.target.value)} style={{ width: "8rem" }} />
      <input type="date" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} />
      <button type="submit" disabled={mutation.isPending}>
        Registrar pago
      </button>
    </form>
  );
}

export function InvoicesPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["invoices", page], queryFn: () => listInvoicesPage(page, PAGE_SIZE) });
  const invoices = data?.items;
  const { data: dashboard } = useQuery({ queryKey: ["finance-dashboard"], queryFn: getFinanceDashboard });
  const { data: projects } = useQuery({ queryKey: ["projects-all"], queryFn: listProjects });

  const [projectId, setProjectId] = useState("");
  const [amount, setAmount] = useState("");
  const [dueDate, setDueDate] = useState("");

  const createMutation = useMutation({
    mutationFn: () => createInvoice({ project_id: projectId, amount: Number(amount), due_date: dueDate || undefined }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["invoices"] });
      queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
      setAmount("");
      setDueDate("");
    },
  });

  const sentMutation = useMutation({
    mutationFn: (id: string) => markInvoiceSent(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["invoices"] }),
  });

  if (isLoading) return <p>Cargando...</p>;

  return (
    <div>
      <h1>Facturación / Reembolsos</h1>
      <p className="page-subtitle">Registro manual de reembolsos por proyecto — un registro por instalación.</p>

      {dashboard && (
        <div className="inline-form" style={{ marginBottom: "1.5rem" }}>
          <span className="status-pill">Facturado: ${dashboard.total_invoiced.toLocaleString()}</span>
          <span className="status-pill status-active">Pagado: ${dashboard.total_paid.toLocaleString()}</span>
          <span className="status-pill">Pendiente: ${dashboard.total_outstanding.toLocaleString()}</span>
          <span className="status-pill status-inactive">Vencido: ${dashboard.total_overdue.toLocaleString()} ({dashboard.overdue_count})</span>
          <span className="status-pill">Vence en 7 días: {dashboard.due_soon_count}</span>
          <button type="button" onClick={() => downloadInvoicesCsv()}>
            Exportar CSV
          </button>
        </div>
      )}

      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (projectId && amount) createMutation.mutate();
        }}
      >
        <select value={projectId} onChange={(e) => setProjectId(e.target.value)} required>
          <option value="">Proyecto...</option>
          {(projects ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <input type="number" step="0.01" placeholder="Monto" value={amount} onChange={(e) => setAmount(e.target.value)} required />
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} placeholder="Fecha límite" />
        <button type="submit" disabled={createMutation.isPending}>
          Crear registro
        </button>
      </form>

      <table className="data-table">
        <thead>
          <tr>
            <th>Factura</th>
            <th>Monto</th>
            <th>Pagado</th>
            <th>Saldo</th>
            <th>Estado</th>
            <th>Vence</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(invoices ?? []).map((inv) => (
            <Fragment key={inv.id}>
              <tr>
                <td>{inv.invoice_number}</td>
                <td>${inv.amount.toLocaleString()}</td>
                <td>${inv.paid_amount.toLocaleString()}</td>
                <td>${inv.balance.toLocaleString()}</td>
                <td>
                  <span className={`status-pill status-${inv.status === "paid" ? "active" : inv.status === "overdue" ? "inactive" : ""}`}>
                    {inv.status}
                  </span>
                </td>
                <td>{inv.due_date ?? "—"}</td>
                <td>
                  {inv.status === "pending" && (
                    <button className="link-button" onClick={() => sentMutation.mutate(inv.id)}>
                      Marcar enviada
                    </button>
                  )}
                </td>
              </tr>
              <tr>
                <td colSpan={7}>
                  <AttachmentsList invoice={inv} />
                  {inv.status !== "paid" && inv.status !== "cancelled" && <PaymentForm invoiceId={inv.id} />}
                </td>
              </tr>
            </Fragment>
          ))}
        </tbody>
      </table>
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
