/** Cobro en línea (Stripe) y banca conectada (Plaid). Spec 2026-10-25-pagos-tarjeta. */
import axios from "axios";
import { apiClient } from "@/lib/apiClient";

export interface PaymentsStatus { online_payments: boolean; bank_feeds: boolean; plaid_env: string }
export const getPaymentsStatus = () => apiClient.get<PaymentsStatus>("/payments/status").then((r) => r.data);

export interface PaymentLink {
  id: string;
  invoice_id: string;
  kind: "full" | "deposit";
  amount: string | null;
  amount_due: string | null;
  status: "active" | "processing" | "paid" | "failed" | "revoked";
  sent_to_email: string | null;
  sent_to_phone: string | null;
  last_sent_at: string | null;
  opened_at: string | null;
  paid_at: string | null;
  created_at: string | null;
  url?: string;
}

export const listPaymentLinks = (invoiceId: string) =>
  apiClient.get<PaymentLink[]>(`/invoices/${invoiceId}/payment-links`).then((r) => r.data);
export const createPaymentLink = (invoiceId: string, body: { kind: "full" | "deposit"; amount?: string;
  send_email?: boolean; send_sms?: boolean; email?: string; phone?: string }) =>
  apiClient.post<PaymentLink>(`/invoices/${invoiceId}/payment-links`, body).then((r) => r.data);
export const revokePaymentLink = (id: string) => apiClient.post(`/payment-links/${id}/revoke`);
export const listProjectOpenInvoices = (projectId: string) =>
  apiClient.get<{ id: string; invoice_number: string; total: string; paid: string; balance: string }[]>(
    `/payments/projects/${projectId}/invoices`).then((r) => r.data);

// --- Página pública (sin sesión) ------------------------------------------------

const publico = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? "/api/v1" });
export interface PublicInvoice {
  company: string;
  invoice_number: string;
  customer_name: string;
  issue_date: string | null;
  due_date: string | null;
  lines: { description: string; quantity: string; amount: string; kind: string }[];
  subtotal: string;
  rebates: string;
  total: string;
  paid: string;
  balance: string;
  amount_requested: string;
  kind: "full" | "deposit";
  status: "open" | "processing" | "paid";
  online_enabled: boolean;
}
export const getPublicInvoice = (token: string) => publico.get<PublicInvoice>(`/public/pay/${token}`).then((r) => r.data);
export const startCheckout = (token: string) =>
  publico.post<{ url: string }>(`/public/pay/${token}/checkout`).then((r) => r.data);

// --- Banca ----------------------------------------------------------------------

export interface BankAccount {
  id: string; name: string; mask: string | null; type: string | null; subtype: string | null;
  current_balance: string | null; available_balance: string | null; active: boolean;
}
export interface BankConnection {
  id: string; institution_name: string; status: "active" | "needs_login" | "disconnected";
  last_synced_at: string | null; last_error: string | null; accounts: BankAccount[];
}
export interface BankTx {
  id: string; date: string; description: string; merchant_name: string | null; pending: boolean;
  spent: string | null; received: string | null;
  account: { id: string; name: string; mask: string | null; type: string | null } | null;
  status: "review" | "categorized" | "excluded"; plaid_category: string | null;
  suggested_category: string | null; suggested_project_id: string | null; suggested_by_rule: boolean;
  category: string | null; project_id: string | null; project_title: string | null;
  expense_id: string | null; matched_type: string | null; matched_id: string | null; memo: string | null;
}
export interface Candidate { type: "expense" | "supplier_payment" | "invoice_payment"; id: string; date: string;
  amount: string; label: string; has_receipt?: boolean }
export interface BankRule {
  id: string; name: string; contains: string; direction: "out" | "in" | "any"; amount_min: string | null;
  amount_max: string | null; account_id: string | null; category: string; project_id: string | null;
  auto_add: boolean; priority: number; active: boolean; memo: string | null;
}

export const getLinkToken = () => apiClient.post<{ link_token: string }>("/bank-feeds/link-token").then((r) => r.data.link_token);
export const listConnections = () => apiClient.get<BankConnection[]>("/bank-feeds/connections").then((r) => r.data);
export const connectBank = (body: { public_token: string; institution_name: string; institution_id?: string }) =>
  apiClient.post<BankConnection>("/bank-feeds/connections", body).then((r) => r.data);
export const syncConnection = (id: string) =>
  apiClient.post<{ added: number; modified: number; removed: number }>(`/bank-feeds/connections/${id}/sync`).then((r) => r.data);
export const setAccountVisible = (id: string, visible: boolean) =>
  apiClient.patch<BankConnection>(`/bank-feeds/accounts/${id}`, { visible }).then((r) => r.data);
export const disconnectBank = (id: string) => apiClient.delete(`/bank-feeds/connections/${id}`);
export const getCounts = () => apiClient.get<Record<string, number>>("/bank-feeds/counts").then((r) => r.data);
export const listBankTx = (status: string, params: { q?: string; account_id?: string; page?: number }) =>
  apiClient.get<BankTx[]>("/bank-feeds/transactions", { params: { status, q: params.q || undefined,
    account_id: params.account_id || undefined, limit: 50, offset: ((params.page ?? 1) - 1) * 50 } })
    .then((r) => ({ rows: r.data, total: Number(r.headers["x-total-count"] ?? r.data.length) }));
export const getCandidates = (id: string) =>
  apiClient.get<Candidate[]>(`/bank-feeds/transactions/${id}/candidates`).then((r) => r.data);
export const addTx = (id: string, body: { category: string; project_id?: string | null; memo?: string | null }) =>
  apiClient.post<BankTx>(`/bank-feeds/transactions/${id}/add`, body).then((r) => r.data);
export const matchTx = (id: string, matched_type: string, matched_id: string) =>
  apiClient.post<BankTx>(`/bank-feeds/transactions/${id}/match`, { matched_type, matched_id }).then((r) => r.data);
export const excludeTx = (id: string, memo?: string) =>
  apiClient.post<BankTx>(`/bank-feeds/transactions/${id}/exclude`, { memo }).then((r) => r.data);
export const undoTx = (id: string) => apiClient.post<BankTx>(`/bank-feeds/transactions/${id}/undo`).then((r) => r.data);
export const acceptTx = (ids: string[]) =>
  apiClient.post<{ accepted: number; skipped: string[] }>("/bank-feeds/transactions/accept", { ids }).then((r) => r.data);
export const listRules = () => apiClient.get<BankRule[]>("/bank-feeds/rules").then((r) => r.data);
export const saveRule = (body: Partial<BankRule> & { name: string; contains: string; category: string }, id?: string) =>
  (id ? apiClient.put<BankRule>(`/bank-feeds/rules/${id}`, body) : apiClient.post<BankRule>("/bank-feeds/rules", body))
    .then((r) => r.data);
export const deleteRule = (id: string) => apiClient.delete(`/bank-feeds/rules/${id}`);

export const EXPENSE_CATEGORIES: Record<string, string> = {
  fuel: "Gasolina", per_diem: "Viáticos", lodging: "Hotel", meals: "Comida", tolls_parking: "Peajes y parqueo",
  small_materials: "Material menor", tools: "Herramienta", other: "Otro",
};

export function usd(v: string | number | null | undefined): string {
  if (v == null || v === "") return "—";
  return Number(v).toLocaleString("en-US", { style: "currency", currency: "USD" });
}
