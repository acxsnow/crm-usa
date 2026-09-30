/**
 * API del módulo 6: cobro de rebate, tablero, configuración por programa,
 * cotizaciones y PDF de facturas. Los errores vienen en español (`detail`) y
 * se muestran con `apiErrorMessage` del módulo 5.
 */
import { useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  BillingDashboard,
  Claim,
  ClaimDetail,
  Eligibility,
  Invoice,
  LineInput,
  ProgramJurisdiction,
  ProgramProfile,
  ProgramRate,
  ProgramRequirement,
  ProgramSummary,
  Quote,
  QuoteDetail,
} from "@/types/billing";

export const billingKeys = {
  dashboard: ["billing-dashboard"] as const,
  claims: ["claims"] as const,
  claim: (id: string) => ["claim", id] as const,
  eligibility: (projectId: string) => ["project-billing", projectId] as const,
  projectClaims: (projectId: string) => ["project-claims", projectId] as const,
  programs: ["billing-programs"] as const,
  program: (id: string, part: string) => ["billing-program", id, part] as const,
  quotes: ["quotes"] as const,
  quote: (id: string) => ["quote", id] as const,
};

/** Tras cualquier cambio de cobro: tablero, listas y el acta del proyecto. */
export function useRefreshBilling() {
  const qc = useQueryClient();
  return (projectId?: string) =>
    Promise.all([
      qc.invalidateQueries({ queryKey: billingKeys.dashboard }),
      qc.invalidateQueries({ queryKey: billingKeys.claims }),
      qc.invalidateQueries({ queryKey: ["claim"] }),
      qc.invalidateQueries({ queryKey: ["invoices"] }),
      ...(projectId
        ? [
            qc.invalidateQueries({ queryKey: billingKeys.eligibility(projectId) }),
            qc.invalidateQueries({ queryKey: billingKeys.projectClaims(projectId) }),
            qc.invalidateQueries({ queryKey: ["project", projectId] }),
          ]
        : []),
    ]);
}

// --- Cobros -------------------------------------------------------------------

export const getEligibility = async (projectId: string) =>
  (await apiClient.get<Eligibility>(`/projects/${projectId}/billing/eligibility`)).data;

export const listClaims = async (params: { project_id?: string; status?: string } = {}) =>
  (await apiClient.get<Claim[]>("/claims", { params })).data;

export const getClaim = async (id: string) => (await apiClient.get<ClaimDetail>(`/claims/${id}`)).data;

export const createClaim = async (projectId: string, programId: string, overrideReason?: string) =>
  (await apiClient.post<ClaimDetail>(`/projects/${projectId}/claims`, {
    program_id: programId, override_reason: overrideReason || undefined,
  })).data;

export const confirmCheck = async (claimId: string, code: string, note?: string) =>
  (await apiClient.post<ClaimDetail>(`/claims/${claimId}/checks/${code}`, { note: note || undefined })).data;

export const removeCheck = async (claimId: string, code: string) =>
  (await apiClient.delete<ClaimDetail>(`/claims/${claimId}/checks/${code}`)).data;

export const submitClaim = async (claimId: string, body: { portal_reference?: string; submitted_on?: string }) =>
  (await apiClient.post<ClaimDetail>(`/claims/${claimId}/submit`, body)).data;

export const rejectClaim = async (claimId: string, body: {
  reason: string; category: string; return_to_technician: boolean;
}) => (await apiClient.post<ClaimDetail>(`/claims/${claimId}/reject`, body)).data;

export const payClaim = async (claimId: string, body: {
  amount: number; paid_on: string; reference?: string; method?: string;
}) => (await apiClient.post<ClaimDetail>(`/claims/${claimId}/payment`, body)).data;

export const withdrawClaim = async (claimId: string, reason: string) =>
  (await apiClient.post<ClaimDetail>(`/claims/${claimId}/withdraw`, { reason })).data;

export const reissueClaimInvoice = async (claimId: string, reason: string) =>
  (await apiClient.post<ClaimDetail>(`/claims/${claimId}/invoice/reissue`, { reason })).data;

export const getBillingDashboard = async () =>
  (await apiClient.get<BillingDashboard>("/billing/dashboard")).data;

// --- PDF ----------------------------------------------------------------------

function openBlob(data: Blob) {
  const url = URL.createObjectURL(data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function openInvoicePdf(invoiceId: string) {
  openBlob((await apiClient.get(`/invoices/${invoiceId}/pdf`, { responseType: "blob" })).data);
}

export async function openInvoicePreview(body: Record<string, unknown>) {
  openBlob((await apiClient.post("/invoices/preview", body, { responseType: "blob" })).data);
}

// --- Configuración por programa --------------------------------------------------

const P = "/billing/programs";

export const listBillingPrograms = async () => (await apiClient.get<ProgramSummary[]>(P)).data;
export const getAutoRules = async () => (await apiClient.get<Record<string, string>>(`${P}/auto-rules`)).data;
export const getProfile = async (id: string) => (await apiClient.get<ProgramProfile>(`${P}/${id}/profile`)).data;
export const updateProfile = async (id: string, body: Partial<ProgramProfile>) =>
  (await apiClient.put<ProgramProfile>(`${P}/${id}/profile`, body)).data;
export const listRates = async (id: string) => (await apiClient.get<ProgramRate[]>(`${P}/${id}/rates`)).data;
export const addRate = async (id: string, body: { amount: number; valid_from: string; valid_to?: string }) =>
  (await apiClient.post<ProgramRate>(`${P}/${id}/rates`, body)).data;
export const closeRate = async (rateId: string, validTo: string) =>
  (await apiClient.patch<ProgramRate>(`${P}/rates/${rateId}/close`, { valid_to: validTo })).data;
export const listJurisdictions = async (id: string) =>
  (await apiClient.get<ProgramJurisdiction[]>(`${P}/${id}/jurisdictions`)).data;
export const addJurisdiction = async (id: string, body: {
  kind: string; value: string; valid_from: string; valid_to?: string;
}) => (await apiClient.post<ProgramJurisdiction>(`${P}/${id}/jurisdictions`, body)).data;
export const deleteJurisdiction = async (jid: string) => apiClient.delete(`${P}/jurisdictions/${jid}`);
export const listRequirements = async (id: string) =>
  (await apiClient.get<ProgramRequirement[]>(`${P}/${id}/requirements`)).data;
export const addRequirement = async (id: string, body: { label?: string; auto_code?: string }) =>
  (await apiClient.post<ProgramRequirement>(`${P}/${id}/requirements`, body)).data;
export const updateRequirement = async (rid: string, body: Partial<ProgramRequirement>) =>
  (await apiClient.patch<ProgramRequirement>(`${P}/requirements/${rid}`, body)).data;

// --- Cotizaciones y borradores -----------------------------------------------------

const Q = "/billing/quotes";

export const listQuotes = async (params: { customer_id?: string; status?: string } = {}) =>
  (await apiClient.get<Quote[]>(Q, { params })).data;
export const getQuote = async (id: string) => (await apiClient.get<QuoteDetail>(`${Q}/${id}`)).data;
export const createQuote = async (body: {
  customer_id?: string; project_id?: string; title?: string; valid_until?: string; notes?: string; lines: LineInput[];
}) => (await apiClient.post<QuoteDetail>(Q, body)).data;
export const updateQuote = async (id: string, body: {
  title?: string; valid_until?: string | null; notes?: string; lines?: LineInput[];
}) => (await apiClient.patch<QuoteDetail>(`${Q}/${id}`, body)).data;
export const sendQuote = async (id: string) => (await apiClient.post<QuoteDetail>(`${Q}/${id}/send`)).data;
export const reviseQuote = async (id: string) => (await apiClient.post<QuoteDetail>(`${Q}/${id}/revise`)).data;
export const acceptQuote = async (id: string) =>
  (await apiClient.post<{ quote: Quote; invoice: Invoice }>(`${Q}/${id}/accept`)).data;
export const rejectQuote = async (id: string, reason: string) =>
  (await apiClient.post<QuoteDetail>(`${Q}/${id}/reject`, { reason })).data;

export const replaceInvoiceLines = async (invoiceId: string, lines: LineInput[]) =>
  (await apiClient.put<Invoice>(`/invoices/${invoiceId}/lines`, { lines })).data;
export const issueInvoice = async (invoiceId: string, dueDate?: string) =>
  (await apiClient.post<Invoice>(`/invoices/${invoiceId}/issue`, { due_date: dueDate || undefined })).data;

// --- Formato -------------------------------------------------------------------------

export const money = (n: number | null | undefined) =>
  (n ?? 0).toLocaleString("en-US", { style: "currency", currency: "USD" });

export function shortDay(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso.length === 10 ? `${iso}T12:00:00` : iso);
  return d.toLocaleDateString("es-CO", { day: "numeric", month: "short", year: "numeric" });
}
