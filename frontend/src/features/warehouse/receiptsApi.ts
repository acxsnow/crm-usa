import { apiClient } from "@/lib/apiClient";
import { fetchPage } from "@/lib/pagination";

/**
 * Recepción de compras, conteos, traslados y ajustes con motivo
 * (cuestionario de bodega, 26 nov 2026). Backend: `warehouse/receipts.py` y
 * `warehouse/service.py` (`register_count`, `count_sheet`).
 */

export interface ReceiptLine {
  id: string;
  item_id: string;
  item_name: string | null;
  sku: string | null;
  has_serial: boolean;
  unit_label: string | null;
  ordered_quantity: string;
  received_quantity: string;
  pending_quantity: string;
  /** Sin costos para quien no los ve. */
  unit_cost?: string;
  /** Precio de la factura más su parte del impuesto y del envío. */
  landed_unit_cost?: string;
  received_value?: string;
}

export interface Receipt {
  id: string;
  number: string;
  status: "abierta" | "recibida" | "cerrada" | "anulada";
  status_label: string;
  supplier_id: string | null;
  supplier_name: string | null;
  document_number: string | null;
  document_date: string | null;
  location_id: string;
  location_name: string | null;
  tax?: string;
  shipping?: string;
  subtotal?: string;
  total?: string;
  received_value?: string;
  note: string | null;
  close_reason: string | null;
  closed_at: string | null;
  supplier_invoice_id: string | null;
  supplier_invoice_number: string | null;
  supplier_invoice_total?: string | null;
  created_by_name: string | null;
  created_at: string | null;
  pending_lines: number;
  lines: ReceiptLine[];
}

export interface ReceiptLineInput {
  item_id: string;
  ordered_quantity: string;
  unit_cost: string;
  received?: string | null;
  serials?: string[] | null;
}

export interface ReceiptInput {
  supplier_id?: string | null;
  supplier_name?: string | null;
  document_number?: string | null;
  document_date?: string | null;
  location_id?: string | null;
  tax?: string | null;
  shipping?: string | null;
  note?: string | null;
  lines: ReceiptLineInput[];
}

export interface SupplierOption { id: string; name: string }
export interface InvoiceCandidate { id: string; number: string; invoice_date: string; total: string; status: string }

export interface WarehouseLocationRow {
  id: string;
  name: string;
  kind: string;
  kind_label: string;
  technician_user_id: string | null;
  active: boolean;
}

export const receiptKeys = {
  all: ["warehouse-receipts"] as const,
  one: (id: string) => ["warehouse-receipts", "uno", id] as const,
  candidates: (id: string) => ["warehouse-receipts", "facturas", id] as const,
  suppliers: ["warehouse-receipt-suppliers"] as const,
  locations: ["warehouse-locations", "activas"] as const,
  countSheet: (locationId: string) => ["warehouse-count-sheet", locationId] as const,
};

export const getReceipt = async (id: string) => (await apiClient.get<Receipt>(`/warehouse/receipts/${id}`)).data;

export const createReceipt = async (data: ReceiptInput) =>
  (await apiClient.post<Receipt>("/warehouse/receipts", data)).data;

export const receiveReceipt = async (id: string, lines: { line_id: string; quantity: string; serials?: string[] | null }[],
  note?: string | null) =>
  (await apiClient.post<Receipt>(`/warehouse/receipts/${id}/receive`, { lines, note })).data;

export const closeReceipt = async (id: string, reason: string) =>
  (await apiClient.post<Receipt>(`/warehouse/receipts/${id}/close`, { reason })).data;

export const setReceiptSupplier = async (id: string, supplierId: string) =>
  (await apiClient.put<Receipt>(`/warehouse/receipts/${id}/supplier`, { supplier_id: supplierId })).data;

/** Las facturas del proveedor por páginas (las más recientes primero). */
export const receiptInvoiceCandidates = (id: string, page: number, pageSize: number) =>
  fetchPage<InvoiceCandidate>(`/warehouse/receipts/${id}/invoice-candidates`, page, pageSize);

export const linkReceiptInvoice = async (id: string, invoiceId: string | null) =>
  (await apiClient.put<Receipt>(`/warehouse/receipts/${id}/invoice`, { supplier_invoice_id: invoiceId })).data;

/** Primera página del buscador de proveedores (como el de artículos: se afina escribiendo). */
export const SUPPLIERS_PER_SEARCH = 20;
export const searchReceiptSuppliers = async (q: string) =>
  (await fetchPage<SupplierOption>("/warehouse/receipts/suppliers", 1, SUPPLIERS_PER_SEARCH, { q: q || undefined })).items;

export const listActiveLocations = async () =>
  (await apiClient.get<WarehouseLocationRow[]>("/warehouse/locations", { params: { active: true, limit: 200 } })).data;

// --- Conteos ----------------------------------------------------------------

export interface CountSheetRow {
  item_id: string;
  name: string;
  sku: string | null;
  brand: string | null;
  category: string;
  category_label: string;
  unit_label: string;
  has_serial: boolean;
  unit_cost?: string;
  system_quantity: string;
}

export interface CountResult {
  location_id: string;
  location_name: string;
  revisados: number;
  sin_cambio: number;
  initial: boolean;
  ajustes: { item_id: string; item_name: string; antes: string; contado: string; diferencia: string;
    movement_type: string; valor: string }[];
}


export const registerCount = async (data: {
  location_id: string; initial: boolean; note?: string | null;
  lines: { item_id: string; counted_quantity: string; unit_cost?: string | null }[];
}) => (await apiClient.post<CountResult>("/warehouse/counts", data)).data;

// --- Traslados y ajustes ----------------------------------------------------

export interface MovementInput {
  item_id: string;
  movement_type: "traslado" | "ajuste";
  quantity: string;
  location_id: string;
  to_location_id?: string | null;
  reason?: string | null;
  note?: string | null;
}

export const createMovement = async (data: MovementInput) =>
  (await apiClient.post("/warehouse/movements", data)).data;
