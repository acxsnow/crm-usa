import { useRef, useState } from "react";
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
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
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
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["invoices", page, extraParams],
    queryFn: () => listInvoicesPage(page, PAGE_SIZE, extraParams),
  });
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

  const filterFields: FilterFieldDef[] = [
    {
      key: "status",
      label: "Estado",
      type: "select",
      options: [
        { value: "pending", label: "Pendiente" },
        { value: "sent", label: "Enviada" },
        { value: "paid", label: "Pagada" },
        { value: "overdue", label: "Vencida" },
        { value: "cancelled", label: "Cancelada" },
      ],
    },
    ...(projects && projects.length > 0
      ? [
          {
            key: "project_id",
            label: "Proyecto",
            type: "select" as const,
            options: projects.map((p) => ({ value: p.id, label: p.title })),
          },
        ]
      : []),
  ];

  const columns: Column<Invoice>[] = [
    { key: "invoice_number", header: "Factura" },
    { key: "amount", header: "Monto", render: (inv) => `$${inv.amount.toLocaleString()}` },
    { key: "paid_amount", header: "Pagado", render: (inv) => `$${inv.paid_amount.toLocaleString()}` },
    { key: "balance", header: "Saldo", render: (inv) => `$${inv.balance.toLocaleString()}` },
    {
      key: "status",
      header: "Estado",
      render: (inv) => (
        <span className={`status-pill status-${inv.status === "paid" ? "active" : inv.status === "overdue" ? "inactive" : ""}`}>
          {inv.status}
        </span>
      ),
    },
    { key: "due_date", header: "Vence", render: (inv) => inv.due_date ?? "—" },
    {
      key: "actions",
      header: "",
      render: (inv) =>
        inv.status === "pending" && (
          <button className="link-button" onClick={() => sentMutation.mutate(inv.id)}>
            Marcar enviada
          </button>
        ),
    },
  ];

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

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        isLoading={isLoading}
        getRowKey={(inv) => inv.id}
        emptyMessage="Sin facturas para mostrar."
        renderDetailRow={(inv) => (
          <>
            <AttachmentsList invoice={inv} />
            {inv.status !== "paid" && inv.status !== "cancelled" && <PaymentForm invoiceId={inv.id} />}
          </>
        )}
      />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
