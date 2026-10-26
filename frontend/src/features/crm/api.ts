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

/** El alta y la edición de datos de contacto exigen la autorización de
 *  tratamiento de datos (`data_consent_accepted`); sin ella el servidor
 *  responde 400 `consent_required`. */
export async function createCustomer(payload: { legal_name: string; data_consent_accepted?: boolean }): Promise<Customer> {
  const res = await apiClient.post<Customer>("/customers", payload);
  return res.data;
}

export async function updateCustomer(
  customerId: string,
  payload: Partial<Customer> & { data_consent_accepted?: boolean }
): Promise<Customer> {
  const res = await apiClient.patch<Customer>(`/customers/${customerId}`, payload);
  return res.data;
}

/** Borra un cliente creado por error: solo si no tiene expedientes, obras, facturas ni cotizaciones. */
export async function deleteCustomer(customerId: string): Promise<void> {
  await apiClient.delete(`/customers/${customerId}`);
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
