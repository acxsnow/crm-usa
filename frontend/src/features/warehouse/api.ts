import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";

/**
 * Bodega: artículos, existencias y movimientos (spec `2026-10-19-control-bodega-design.md`).
 *
 * Los catálogos (categorías, unidades) vienen del backend y no se repiten aquí:
 * el cliente los cambia en su Excel y la pantalla se actualiza sola.
 */

export interface WarehouseCatalogs {
  categories: Record<string, string>;
  units: Record<string, string>;
  movement_types: Record<string, string>;
  location_kinds: Record<string, string>;
  release_statuses: Record<string, string>;
  line_origins: Record<string, string>;
}

/** Cuánto hay de un artículo en una ubicación concreta (bodega o camioneta). */
export interface StockAtLocation {
  location_id: string;
  name: string;
  kind: string;
  quantity: string;
}

export interface WarehouseItem {
  id: string;
  name: string;
  sku: string | null;
  category: string;
  category_label: string;
  unit: string;
  unit_label: string;
  unit_cost: string;
  supplier_name: string | null;
  has_serial: boolean;
  min_quantity: string | null;
  notes: string | null;
  active: boolean;
  total_quantity: string;
  by_location: StockAtLocation[];
  below_minimum: boolean;
  value: string;
}

/** Un movimiento del libro: la entrada, la salida, el traslado o el ajuste. */
export interface WarehouseMovement {
  id: string;
  item_id: string;
  item_name: string | null;
  unit_label: string | null;
  location_id: string;
  location_name: string | null;
  vendor_location_id: string | null;
  movement_type: string;
  movement_type_label: string;
  quantity: string;
  unit_cost: string | null;
  amount: string | null;
  movement_date: string | null;
  reference: string | null;
  note: string | null;
  project_id: string | null;
  created_at: string | null;
}

export interface ReleaseLine {
  id: string;
  item_id: string;
  item_name: string | null;
  sku: string | null;
  unit: string | null;
  unit_label: string | null;
  unit_cost: string | null;
  quantity_requested: string;
  quantity_delivered: string | null;
  pending_quantity: string;
  spec_label: string | null;
  notes: string | null;
  origin: string;
}

/** Una orden de salida de bodega (punto 1 del cuestionario del 19 de octubre). */
export interface WarehouseRelease {
  id: string;
  number: string | null;
  status: string;
  project_id: string | null;
  location_id: string;
  location_name: string | null;
  requested_by_user_id: string | null;
  technician_user_id: string | null;
  needed_on: string | null;
  note: string | null;
  submitted_at: string | null;
  authorized_by_user_id: string | null;
  authorized_at: string | null;
  reject_reason: string | null;
  delivered_by_user_id: string | null;
  delivered_at: string | null;
  shortage_note: string | null;
  created_at: string | null;
  lines: ReleaseLine[];
}

/** Lo que se pidió y no había en bodega al entregar. */
export interface Shortage {
  line_id: string;
  item_id: string;
  pedida: string;
  entregada: string;
  motivo: string;
}

export interface DeliverResult extends WarehouseRelease {
  faltantes: Shortage[];
}

export interface ReleaseLineInput {
  item_id: string;
  quantity: string;
  spec_label?: string | null;
  notes?: string | null;
}

export interface ReleaseInput {
  project_id?: string | null;
  technician_user_id?: string | null;
  location_id?: string | null;
  needed_on?: string | null;
  note?: string | null;
  lines: ReleaseLineInput[];
}

export interface ImportResult {
  creados: number;
  actualizados: number;
  omitidos: number;
  conteo_inicial: number;
  errores: { fila: number; error: string }[];
  sheet: string;
  rows_read: number;
}

export const warehouseCatalogs = async () =>
  (await apiClient.get<WarehouseCatalogs>("/warehouse/catalogs")).data;

export const warehouseKeys = {
  catalogs: ["warehouse-catalogs"] as const,
  items: ["warehouse-items"] as const,
  stock: ["warehouse-stock"] as const,
  summary: ["warehouse-stock-summary"] as const,
  movements: ["warehouse-movements"] as const,
  releases: ["warehouse-releases"] as const,
  pendingReleases: ["warehouse-releases-pending"] as const,
};

export const listStockPage = (page: number, pageSize: number, params: Record<string, string | boolean | undefined> = {}) =>
  fetchPage<WarehouseItem>("/warehouse/stock", page, pageSize, params);

export const listItemsPage = (page: number, pageSize: number, params: Record<string, string | boolean | undefined> = {}) =>
  fetchPage<WarehouseItem>("/warehouse/items", page, pageSize, params);

export const stockSummary = async () =>
  (await apiClient.get<{ low_count: number }>("/warehouse/stock/summary")).data;

// --- Órdenes de salida -------------------------------------------------------
//
// Los listados (`/warehouse/releases`, `/warehouse/releases/pending`,
// `/warehouse/movements`) se piden con `usePaginatedQuery`, como el resto de las
// tablas: así traen solo la página que se ve.

export const createRelease = async (data: ReleaseInput) =>
  (await apiClient.post<WarehouseRelease>("/warehouse/releases", data)).data;

export const submitRelease = async (id: string) =>
  (await apiClient.post<WarehouseRelease>(`/warehouse/releases/${id}/submit`)).data;

export const approveRelease = async (id: string) =>
  (await apiClient.post<WarehouseRelease>(`/warehouse/releases/${id}/approve`)).data;

export const rejectRelease = async (id: string, reason: string) =>
  (await apiClient.post<WarehouseRelease>(`/warehouse/releases/${id}/reject`, { reason })).data;

export const deliverRelease = async (id: string, note?: string | null) =>
  (await apiClient.post<DeliverResult>(`/warehouse/releases/${id}/deliver`, { note: note || null })).data;

export const getItem = async (id: string) =>
  (await apiClient.get<WarehouseItem>(`/warehouse/items/${id}`)).data;

/** Crea o actualiza un artículo. `id` vacío = nuevo. */
export const saveItem = async (id: string | null, data: Record<string, unknown>) =>
  id
    ? (await apiClient.put<WarehouseItem>(`/warehouse/items/${id}`, data)).data
    : (await apiClient.post<WarehouseItem>("/warehouse/items", data)).data;

/**
 * Sube el Excel del cliente (hoja «Catálogo»). Con `replaceStock` la cantidad
 * del archivo corrige la existencia con un ajuste; sin él solo se cargan los
 * artículos nuevos y se actualizan los datos de los que ya existen.
 */
export const importCatalog = async (file: File, replaceStock: boolean) => {
  const form = new FormData();
  form.append("file", file);
  const { data } = await apiClient.post<ImportResult>("/warehouse/import", form, {
    params: { replace_stock: replaceStock },
  });
  return data;
};
