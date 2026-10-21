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
  budget_categories: Record<string, string>;
  budget_statuses: Record<string, string>;
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

/** Un renglón de la lista predefinida: el material, cuánto y de qué calibre. */
export interface WarehouseKitItem {
  id: string;
  item_id: string;
  item_name: string | null;
  sku: string | null;
  unit: string | null;
  unit_label: string | null;
  quantity: string;
  unit_cost: string | null;
  spec_label: string | null;
  section: string | null;
  is_required: boolean;
  notes: string | null;
}

/**
 * Una lista predefinida por tipo de trabajo (punto 2 del cuestionario).
 *
 * Es una plantilla: al aplicarla, sus renglones se copian a la orden de salida y
 * de ahí en adelante se ajustan en la copia. Cambiar la lista no cambia lo que
 * ya se pidió.
 */
export interface WarehouseKit {
  id: string;
  name: string;
  project_type: string | null;
  description: string | null;
  active: boolean;
  created_at: string | null;
  items: WarehouseKitItem[];
}

export interface KitItemInput {
  item_id: string;
  quantity: string;
  spec_label?: string | null;
  section?: string | null;
  is_required?: boolean;
  notes?: string | null;
}

export interface KitInput {
  name: string;
  project_type?: string | null;
  description?: string | null;
  active?: boolean;
  items: KitItemInput[];
}

export interface ApplyKitResult extends WarehouseRelease {
  kit_name: string;
  agregadas: number;
  omitidas: number;
}

/** Un renglón del presupuesto: qué se estimó, cuánto y a qué costo. */
export interface BudgetLine {
  id: string;
  category: string;
  item_id: string | null;
  item_name: string | null;
  sku: string | null;
  description: string;
  quantity: string;
  unit: string | null;
  unit_label: string | null;
  unit_cost: string;
  amount: string;
  notes: string | null;
}

/**
 * El presupuesto de una obra (punto 3 del cuestionario).
 *
 * `borrador` se edita; `aprobado` es el que cuenta para la comparación contra lo
 * real; `reemplazado` es el que quedó atrás cuando se aprobó otro.
 */
export interface ProjectBudget {
  id: string;
  project_id: string;
  status: string;
  notes: string | null;
  created_at: string | null;
  approved_at: string | null;
  approved_by_user_id: string | null;
  total: string;
  by_category: Record<string, string>;
  lines: BudgetLine[];
}

export interface BudgetLineInput {
  category: string;
  item_id?: string | null;
  description?: string | null;
  quantity: string;
  unit?: string | null;
  unit_cost?: string | null;
  notes?: string | null;
}

export interface BudgetInput {
  project_id?: string | null;
  notes?: string | null;
  lines: BudgetLineInput[];
}

export interface ApplyKitToBudgetResult extends ProjectBudget {
  kit_name: string;
  agregadas: number;
  omitidas: number;
}

/** Una fila de «estimado contra real»: la categoría, el estimado, el real y su desviación. */
export interface BudgetVsActualRow {
  category: string;
  label: string;
  estimated: string;
  actual: string;
  deviation: string;
  deviation_pct: number | null;
}

export interface BudgetVsActual {
  project_id: string;
  budget_id: string | null;
  budget_status: string | null;
  rows: BudgetVsActualRow[];
  totals: { estimated: string; actual: string; deviation: string; deviation_pct: number | null };
}

/** Una fila de compras sugeridas: lo presupuestado por venir menos la existencia. */
export interface PurchasingRow {
  item_id: string;
  item_name: string | null;
  sku: string | null;
  unit: string | null;
  budgeted: string;
  in_stock: string;
  to_buy: string;
  unit_cost: string;
  estimated_cost: string;
  below_minimum: boolean;
}

export interface PurchasingReport {
  rows: PurchasingRow[];
  totals: { budgeted: string; to_buy: string; items: number };
}

/** Un material de la jornada: lo que se usó ese día y de dónde salió. */
export interface DayLogMaterial {
  id: string;
  item_id: string | null;
  item_name: string | null;
  sku: string | null;
  description: string;
  quantity: string;
  unit: string | null;
  unit_label: string | null;
  location_id: string | null;
  location_name: string | null;
  movement_id: string | null;
  /** Ya descontó la camioneta: el movimiento quedó en el libro y la línea no se edita. */
  descontada: boolean;
  notes: string | null;
}

/**
 * Una jornada del diario de obra (punto 4 del cuestionario).
 *
 * El técnico vive en la jornada y no en el proyecto: la misma obra tiene uno
 * distinto cada día, y más de una jornada es una obra de varios días. Los
 * gastos del día se leen de los gastos de la obra, no se capturan aquí.
 */
export interface DayLog {
  id: string;
  project_id: string;
  log_date: string | null;
  technician_user_id: string | null;
  technician_name: string | null;
  crew: string | null;
  hours: string | null;
  work_done: string | null;
  progress_note: string | null;
  missing_materials: string | null;
  next_day_plan: string | null;
  incidents: string | null;
  created_at: string | null;
  materials: DayLogMaterial[];
  expenses: { count: number; amount: string };
}

export interface DayLogMaterialInput {
  id?: string | null;
  item_id?: string | null;
  description?: string | null;
  quantity: string;
  unit?: string | null;
  /** De dónde salió: la camioneta. Sin ubicación la línea solo se anota. */
  location_id?: string | null;
  notes?: string | null;
}

export interface DayLogInput {
  log_date: string;
  technician_user_id?: string | null;
  crew?: string | null;
  hours?: string | null;
  work_done?: string | null;
  progress_note?: string | null;
  missing_materials?: string | null;
  next_day_plan?: string | null;
  incidents?: string | null;
  materials: DayLogMaterialInput[];
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
  kits: ["warehouse-kits"] as const,
  budgets: ["warehouse-budgets"] as const,
  projectBudget: (projectId: string) => ["warehouse-project-budget", projectId] as const,
  budgetVsActual: (projectId: string) => ["warehouse-budget-vs-actual", projectId] as const,
  dayLogs: (projectId: string) => ["warehouse-day-logs", projectId] as const,
  purchasing: ["warehouse-purchasing"] as const,
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

// --- Listas predefinidas por tipo de trabajo (punto 2) -----------------------
//
// Igual que las órdenes: el listado se pide con `usePaginatedQuery`.

export const listKitsPage = (page: number, pageSize: number, params: Record<string, string | boolean | undefined> = {}) =>
  fetchPage<WarehouseKit>("/warehouse/kits", page, pageSize, params);

export const getKit = async (id: string) =>
  (await apiClient.get<WarehouseKit>(`/warehouse/kits/${id}`)).data;

/** Crea o reemplaza la lista completa. `id` vacío = nueva. */
export const saveKit = async (id: string | null, data: KitInput) =>
  id
    ? (await apiClient.put<WarehouseKit>(`/warehouse/kits/${id}`, data)).data
    : (await apiClient.post<WarehouseKit>("/warehouse/kits", data)).data;

export const deleteKit = async (id: string) => {
  await apiClient.delete(`/warehouse/kits/${id}`);
};

/** Copia la lista a un borrador de orden de salida. */
export const applyKit = async (kitId: string, releaseId: string) =>
  (await apiClient.post<ApplyKitResult>(`/warehouse/kits/${kitId}/apply`, { release_id: releaseId })).data;

// --- Presupuesto del proyecto y costo real (punto 3) -------------------------
//
// El presupuesto es de la obra, no de la bodega: se arma aquí y el gasto real
// sale de las salidas valoradas, los gastos aprobados y las compras directas.

export const listBudgetsPage = (page: number, pageSize: number, params: Record<string, string | boolean | undefined> = {}) =>
  fetchPage<ProjectBudget>("/warehouse/budgets", page, pageSize, params);

/** El presupuesto vigente de la obra: `null` cuando todavía no hay ninguno. */
export const getProjectBudget = async (projectId: string) =>
  (await apiClient.get<ProjectBudget | null>(`/warehouse/projects/${projectId}/budget`)).data;

/** Crea o reemplaza el borrador completo. `id` vacío = nuevo. */
export const saveBudget = async (id: string | null, data: BudgetInput) =>
  id
    ? (await apiClient.put<ProjectBudget>(`/warehouse/budgets/${id}`, data)).data
    : (await apiClient.post<ProjectBudget>("/warehouse/budgets", data)).data;

export const approveBudget = async (id: string) =>
  (await apiClient.post<ProjectBudget>(`/warehouse/budgets/${id}/approve`)).data;

export const deleteBudget = async (id: string) => {
  await apiClient.delete(`/warehouse/budgets/${id}`);
};

/** Copia una lista predefinida al borrador del presupuesto. */
export const applyKitToBudget = async (budgetId: string, kitId: string) =>
  (await apiClient.post<ApplyKitToBudgetResult>(`/warehouse/budgets/${budgetId}/apply-kit`, { kit_id: kitId })).data;

export const getBudgetVsActual = async (projectId: string) =>
  (await apiClient.get<BudgetVsActual>(`/warehouse/projects/${projectId}/budget-vs-actual`)).data;

export const getPurchasing = async () =>
  (await apiClient.get<PurchasingReport>("/warehouse/purchasing")).data;

// --- Diario de obra (punto 4) -----------------------------------------------
//
// Las jornadas de la obra: qué se hizo cada día, con qué técnico, qué material
// salió de la camioneta y qué quedó pendiente para el día siguiente.

export const listDayLogsPage = (projectId: string, page: number, pageSize: number) =>
  fetchPage<DayLog>(`/warehouse/projects/${projectId}/day-logs`, page, pageSize);

/** Registra o corrige la jornada. `id` vacío = nueva. */
export const saveDayLog = async (projectId: string, id: string | null, data: DayLogInput) =>
  id
    ? (await apiClient.put<DayLog>(`/warehouse/projects/${projectId}/day-logs/${id}`, data)).data
    : (await apiClient.post<DayLog>(`/warehouse/projects/${projectId}/day-logs`, data)).data;

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
