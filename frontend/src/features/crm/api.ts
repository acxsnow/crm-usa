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


// --- Catálogos -------------------------------------------------------------

export async function listFunderStatuses(): Promise<FunderStatus[]> {
  const res = await apiClient.get<FunderStatus[]>("/funder-statuses");
  return res.data;
}
