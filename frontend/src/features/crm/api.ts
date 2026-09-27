import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";
import type { Customer, Customer360, FunderStatus } from "@/types/crm";

// --- Customers ---------------------------------------------------------

export async function listCustomers(): Promise<Customer[]> {
  const res = await apiClient.get<Customer[]>("/customers");
  return res.data;
}

export async function listCustomersPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Customer>> {
  return fetchPage<Customer>("/customers", page, pageSize, extraParams);
}

export async function createCustomer(payload: { legal_name: string }): Promise<Customer> {
  const res = await apiClient.post<Customer>("/customers", payload);
  return res.data;
}

export async function updateCustomer(customerId: string, payload: Partial<Customer>): Promise<Customer> {
  const res = await apiClient.patch<Customer>(`/customers/${customerId}`, payload);
  return res.data;
}

export async function getCustomerTimeline(customerId: string): Promise<Customer360> {
  const res = await apiClient.get<Customer360>(`/customers/${customerId}/timeline`);
  return res.data;
}

export interface ProgramFormField { id: string; program_code: string; form_version: string; field_key: string; label: string; field_type: string; required: boolean; options?: string[] | null; sort_order: number; active: boolean; }
export interface Application { id: string; customer_id?: string | null; program_code: string; form_version: string; status: string; answers: Record<string, unknown>; terms_accepted: boolean; terms_version?: string | null; customer_signed_at?: string | null; salesperson_signed_at?: string | null; review_notes?: string | null; created_at: string; }
export async function getProgramFormFields(programCode: string): Promise<ProgramFormField[]> { return (await apiClient.get<ProgramFormField[]>("/program-form-fields", { params: { program_code: programCode } })).data; }
export async function createApplication(payload: { customer_id?: string; program_code: string; answers: Record<string, unknown>; terms_version: string; terms_accepted: boolean }): Promise<Application> { return (await apiClient.post<Application>("/applications", payload)).data; }
export async function signApplication(applicationId: string, customerName: string, signatureBase64: string): Promise<Application> { return (await apiClient.post<Application>(`/applications/${applicationId}/customer-sign`, { customer_name: customerName, signature_base64: signatureBase64 })).data; }
export async function listApplicationsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Application>> {
  return fetchPage<Application>("/applications", page, pageSize, extraParams);
}
export async function updateApplication(applicationId: string, payload: { status?: string; review_notes?: string }): Promise<Application> { return (await apiClient.patch<Application>(`/applications/${applicationId}`, payload)).data; }

// --- Catálogos -------------------------------------------------------------

export async function listFunderStatuses(): Promise<FunderStatus[]> {
  const res = await apiClient.get<FunderStatus[]>("/funder-statuses");
  return res.data;
}
