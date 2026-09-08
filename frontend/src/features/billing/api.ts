import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";
import type { FinanceDashboard, Invoice, InvoiceAttachment } from "@/types/billing";

export async function listInvoices(): Promise<Invoice[]> {
  const res = await apiClient.get<Invoice[]>("/invoices");
  return res.data;
}

export async function listInvoicesPage(page: number, pageSize: number): Promise<Page<Invoice>> {
  return fetchPage<Invoice>("/invoices", page, pageSize);
}

export async function createInvoice(payload: {
  project_id: string;
  amount: number;
  funder_program?: string;
  due_date?: string;
  notes?: string;
}): Promise<Invoice> {
  const res = await apiClient.post<Invoice>("/invoices", payload);
  return res.data;
}

export async function markInvoiceSent(invoiceId: string): Promise<Invoice> {
  const res = await apiClient.post<Invoice>(`/invoices/${invoiceId}/mark-sent`, {});
  return res.data;
}

export async function recordInvoicePayment(
  invoiceId: string,
  payload: { amount: number; paid_at: string; method?: string; reference?: string }
): Promise<Invoice> {
  const res = await apiClient.post<Invoice>(`/invoices/${invoiceId}/payments`, payload);
  return res.data;
}

export async function getFinanceDashboard(): Promise<FinanceDashboard> {
  const res = await apiClient.get<FinanceDashboard>("/finance/dashboard");
  return res.data;
}

export async function uploadInvoiceAttachment(invoiceId: string, file: File): Promise<InvoiceAttachment> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiClient.post<InvoiceAttachment>(`/invoices/${invoiceId}/attachments`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function fetchInvoiceAttachmentObjectUrl(attachmentId: string): Promise<string> {
  const res = await apiClient.get(`/invoice-attachments/${attachmentId}/file`, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}

export async function downloadInvoicesCsv(): Promise<void> {
  const res = await apiClient.get("/invoices-export.csv", { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = "invoices.csv";
  link.click();
  URL.revokeObjectURL(url);
}
