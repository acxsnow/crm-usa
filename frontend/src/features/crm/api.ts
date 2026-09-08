import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";
import type {
  Customer,
  Customer360,
  FunderStatus,
  ImportSummary,
  Lead,
  LeadCreateResult,
  Opportunity,
  PipelineStage,
  Quote,
} from "@/types/crm";

// --- Leads -----------------------------------------------------------------

export async function listLeads(): Promise<Lead[]> {
  const res = await apiClient.get<Lead[]>("/leads");
  return res.data;
}

export async function listLeadsPage(page: number, pageSize: number, status?: Lead["status"]): Promise<Page<Lead>> {
  return fetchPage<Lead>("/leads", page, pageSize, { status });
}

export async function createLead(payload: Partial<Lead>): Promise<LeadCreateResult> {
  const res = await apiClient.post<LeadCreateResult>("/leads", payload);
  return res.data;
}

export async function convertLead(leadId: string): Promise<{ customer_id: string; opportunity_id: string }> {
  const res = await apiClient.post(`/leads/${leadId}/convert`, {});
  return res.data;
}

export async function importLeadsCsv(file: File, columnMapping: Record<string, string>): Promise<ImportSummary> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("column_mapping", JSON.stringify(columnMapping));
  const res = await apiClient.post<ImportSummary>("/leads/import", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

// --- Customers ---------------------------------------------------------

export async function listCustomers(): Promise<Customer[]> {
  const res = await apiClient.get<Customer[]>("/customers");
  return res.data;
}

export async function listCustomersPage(page: number, pageSize: number): Promise<Page<Customer>> {
  return fetchPage<Customer>("/customers", page, pageSize);
}

export async function createCustomer(payload: { legal_name: string }): Promise<Customer> {
  const res = await apiClient.post<Customer>("/customers", payload);
  return res.data;
}

export async function getCustomerTimeline(customerId: string): Promise<Customer360> {
  const res = await apiClient.get<Customer360>(`/customers/${customerId}/timeline`);
  return res.data;
}

// --- Pipeline / Opportunities -----------------------------------------

export async function listPipelineStages(): Promise<PipelineStage[]> {
  const res = await apiClient.get<PipelineStage[]>("/pipeline-stages");
  return res.data;
}

export async function listOpportunities(): Promise<Opportunity[]> {
  // The pipeline board groups every opportunity by stage rather than
  // paginating a flat list, so it fetches up to the API's max page size
  // (500) in one go instead of the 100-row default — a kanban view with a
  // "next page" control isn't a real UX, but silently truncating an org's
  // active pipeline at 100 would be a real bug once they grow past that.
  const res = await apiClient.get<Opportunity[]>("/opportunities", { params: { limit: 500 } });
  return res.data;
}

export async function listFunderStatuses(): Promise<FunderStatus[]> {
  const res = await apiClient.get<FunderStatus[]>("/funder-statuses");
  return res.data;
}

export async function updateOpportunityFunderStatus(opportunityId: string, funderStatusCode: string): Promise<Opportunity> {
  const res = await apiClient.patch<Opportunity>(`/opportunities/${opportunityId}`, {
    funder_status_code: funderStatusCode,
  });
  return res.data;
}

export async function changeOpportunityStage(
  opportunityId: string,
  stageCode: string,
  lossReason?: string
): Promise<Opportunity> {
  const res = await apiClient.post<Opportunity>(`/opportunities/${opportunityId}/change-stage`, {
    stage_code: stageCode,
    loss_reason: lossReason,
  });
  return res.data;
}

// --- Quotes ---------------------------------------------------------------

export async function listQuotes(): Promise<Quote[]> {
  const res = await apiClient.get<Quote[]>("/quotes");
  return res.data;
}
