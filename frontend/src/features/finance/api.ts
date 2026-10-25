/** API de gastos de campo, proveedores y pagos, conciliación, rentabilidad, reportes y permisos. */
import { apiClient } from "@/lib/apiClient";

export type Dict = Record<string, string>;

// --- Gastos de campo ---------------------------------------------------------

export interface Expense {
  id: string; user_id: string; user_name: string | null; project_id: string | null; project_title: string | null;
  expense_date: string; category: string; category_label: string; amount: string; description: string;
  payment_method: string; payment_label: string | null; status: "submitted" | "approved" | "rejected" | "reimbursed";
  has_receipt: boolean; reviewed_by: string | null; reviewed_at: string | null; review_notes: string | null;
  reimbursed_at: string | null; reimbursement_reference: string | null;
}
export interface ExpenseInput { expense_date: string; category: string; amount: string; description: string;
  payment_method: string; project_id: string | null }

export const expenseCatalogs = async () =>
  (await apiClient.get<{ categories: Dict; payment_methods: Dict; statuses: Dict }>("/expenses/catalogs")).data;
export async function createExpense(data: ExpenseInput, receipt: File) {
  const f = new FormData();
  f.append("data", JSON.stringify(data));
  f.append("receipt", receipt);
  return (await apiClient.post<Expense>("/expenses", f, { headers: { "Content-Type": "multipart/form-data" } })).data;
}
export const deleteExpense = async (id: string) => (await apiClient.delete(`/expenses/${id}`)).data;
export const reviewExpense = async (id: string, approve: boolean, notes?: string) =>
  (await apiClient.post<Expense>(`/expenses/${id}/review`, { approve, notes: notes || null })).data;
export const reimburseExpense = async (id: string, paid_on: string, reference?: string) =>
  (await apiClient.post<Expense>(`/expenses/${id}/reimburse`, { paid_on, reference: reference || null })).data;

/** Abre un archivo protegido (recibo, factura, comprobante) en otra pestaña. */
export async function openFile(path: string) {
  const r = await apiClient.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

/** Descarga un archivo (CSV) que exige sesión. */
export async function downloadFile(path: string, filename: string, params: Record<string, string | undefined> = {}) {
  const r = await apiClient.get(path, { responseType: "blob", params });
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

// --- Proveedores y cuentas por pagar ------------------------------------------

export interface Supplier {
  id: string; name: string; legal_name: string | null; tax_id: string | null; kinds: string[]; contact_name: string | null;
  phone: string | null; email: string | null; address: string | null; states: string[]; payment_terms_days: number;
  payment_method: string | null; bank_details: string | null; license_number: string | null;
  license_expires_on: string | null; insurance_expires_on: string | null; w9_on_file: boolean; notes: string | null;
  active: boolean; balance: string | null;
  documents?: { id: string; kind: string; kind_label: string; filename: string | null; expires_on: string | null; uploaded_at: string | null }[];
}
export interface InvoiceLine { description: string; category: string; quantity: string; unit_cost: string; amount?: string;
  project_id: string | null; project_title?: string | null }
export interface SupplierInvoice {
  id: string; supplier_id: string; supplier_name: string | null; number: string; invoice_date: string; due_date: string;
  subtotal: string; tax: string; shipping: string; total: string; paid: string; balance: string;
  status: "pending_approval" | "approved" | "partially_paid" | "paid" | "void"; overdue_days: number;
  scheduled_payment_date: string | null; notes: string | null; void_reason: string | null; has_file: boolean;
  approvals: { user_name: string | null; capacity: string; approved_at: string }[]; approvals_missing: string[];
  lines: InvoiceLine[];
}
export interface SupplierPayment {
  id: string; supplier_id: string; supplier_name: string | null; paid_on: string; amount: string; method: string;
  method_label: string | null; reference: string | null; bank_account: string | null; notes: string | null; has_file: boolean;
  allocations: { invoice_id: string; amount: string }[];
}
export interface Aging {
  buckets: { key: string; label: string }[];
  rows: (Record<string, string | number> & { supplier_id: string; supplier_name: string; total: string; invoices: number })[];
  totals: Record<string, string>; as_of: string;
}
export interface PayablesCatalogs { supplier_kinds: Dict; payment_methods: Dict; cost_categories: Dict; document_kinds: Dict;
  invoice_statuses: Dict }
export interface FinanceSettings { two_approval_threshold: string; due_alert_days: number; document_alert_days: number;
  max_expense_amount: string }

export const payablesCatalogs = async () => (await apiClient.get<PayablesCatalogs>("/payables/catalogs")).data;
export const getSupplier = async (id: string) => (await apiClient.get<Supplier>(`/payables/suppliers/${id}`)).data;
export const saveSupplier = async (s: Partial<Supplier>) =>
  (s.id ? await apiClient.put<Supplier>(`/payables/suppliers/${s.id}`, s) : await apiClient.post<Supplier>("/payables/suppliers", s)).data;
export const importSuppliers = async (text: string) =>
  (await apiClient.post<{ created: number; skipped: number; invalid: string[] }>("/payables/suppliers/import", { text })).data;
export async function uploadSupplierDocument(id: string, kind: string, file: File, expires_on?: string) {
  const f = new FormData();
  f.append("kind", kind);
  f.append("file", file);
  if (expires_on) f.append("expires_on", expires_on);
  return (await apiClient.post(`/payables/suppliers/${id}/documents`, f, { headers: { "Content-Type": "multipart/form-data" } })).data;
}
export async function createInvoice(data: Record<string, unknown>, file?: File | null) {
  const f = new FormData();
  f.append("data", JSON.stringify(data));
  if (file) f.append("file", file);
  return (await apiClient.post<SupplierInvoice>("/payables/invoices", f, { headers: { "Content-Type": "multipart/form-data" } })).data;
}
export const approveInvoice = async (id: string, notes?: string) =>
  (await apiClient.post<SupplierInvoice>(`/payables/invoices/${id}/approve`, { notes: notes || null })).data;
export const scheduleInvoice = async (id: string, date: string | null) =>
  (await apiClient.post<SupplierInvoice>(`/payables/invoices/${id}/schedule`, { scheduled_payment_date: date })).data;
export const voidInvoice = async (id: string, reason: string) =>
  (await apiClient.post<SupplierInvoice>(`/payables/invoices/${id}/void`, { reason })).data;
export const openInvoices = async (supplierId: string) => (await apiClient.get<SupplierInvoice[]>("/payables/invoices",
  { params: { supplier_id: supplierId, status: "open", limit: 200 } })).data;
export async function recordPayment(data: Record<string, unknown>, file?: File | null) {
  const f = new FormData();
  f.append("data", JSON.stringify(data));
  if (file) f.append("file", file);
  return (await apiClient.post<SupplierPayment>("/payables/payments", f, { headers: { "Content-Type": "multipart/form-data" } })).data;
}
export const payablesAging = async () => (await apiClient.get<Aging>("/payables/aging")).data;
export const getFinanceSettings = async () => (await apiClient.get<FinanceSettings>("/finance/settings")).data;
export const putFinanceSettings = async (s: FinanceSettings) => (await apiClient.put<FinanceSettings>("/finance/settings", s)).data;

// --- Rentabilidad y conciliación ---------------------------------------------

export interface ProfitRow {
  project_id: string; title: string; status: string; completed_date: string | null; case_number: string | null;
  program: string | null; expected: string; collected: string; costs: string; cost_breakdown: Dict; margin: string;
  expected_margin: string; margin_pct: number | null;
  /** Margen del estimado de la obra (costo del trabajo); null si no tiene estimado o precio. */
  estimated_margin_pct: number | null;
}
export interface Profitability { cost_labels: Dict; rows: ProfitRow[]; totals: Record<string, string | number | null> }
export const profitabilityReport = async (params: Record<string, string | undefined>) =>
  (await apiClient.get<Profitability>("/finance/profitability", { params })).data;

export interface BankLine { id: string; statement_id: string; date: string; description: string; reference: string | null;
  amount: string; status: "unmatched" | "matched" | "ignored"; matched_type: string | null; matched_label: string | null;
  matched_id: string | null; auto_matched: boolean; notes: string | null }
export interface Candidate { type: string; id: string; date: string; amount: string; label: string }
export async function importStatement(account_label: string, file: File) {
  const f = new FormData();
  f.append("account_label", account_label);
  f.append("file", file);
  return (await apiClient.post<{ lines: number; auto_matched: number; invalid: string[] }>("/reconciliation/statements", f,
    { headers: { "Content-Type": "multipart/form-data" } })).data;
}
export const reconSummary = async () =>
  (await apiClient.get<{ lines: number; unmatched: number; matched: number; ignored: number }>("/reconciliation/summary")).data;
export const lineCandidates = async (id: string) =>
  (await apiClient.get<{ items: Candidate[] }>(`/reconciliation/lines/${id}/candidates`)).data.items;
export const matchLine = async (id: string, matched_type: string, matched_id: string) =>
  (await apiClient.post<BankLine>(`/reconciliation/lines/${id}/match`, { matched_type, matched_id })).data;
export const ignoreLine = async (id: string, notes: string) =>
  (await apiClient.post<BankLine>(`/reconciliation/lines/${id}/ignore`, { notes })).data;
export const unmatchLine = async (id: string) => (await apiClient.post<BankLine>(`/reconciliation/lines/${id}/unmatch`)).data;

// --- Reportes ------------------------------------------------------------------

export interface Report {
  title: string; range: [string, string];
  kpis: { label: string; value: string | number | null }[];
  sections: { title: string; columns: string[]; rows: (string | number)[][] }[];
}
export const getReport = async (kind: string, params: Record<string, string | undefined>) =>
  (await apiClient.get<Report>(`/reports/${kind}`, { params })).data;

// --- Permisos e inspecciones ---------------------------------------------------

export interface PermitRow { id: string; project_id: string; project_title: string | null; jurisdiction: string;
  permit_number: string | null; permit_type: string | null; status: string; status_label: string; filed_on: string | null;
  approved_on: string | null; expires_on: string | null; days_to_expiry: number | null }
export interface InspectionRow { id: string; project_id: string; project_title: string | null; scheduled_for: string;
  inspector_name: string | null; result: string; result_label: string; result_recorded_at: string | null;
  observations: string | null }

export const money = (v: string | number | null | undefined) =>
  v === null || v === undefined || v === ""
    ? "—"
    // D-002: con estilo de moneda el signo va antes del símbolo («-$80,705.00», no «$-80,705.00»).
    : Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" });
export const today = () => new Date().toLocaleDateString("en-CA");
