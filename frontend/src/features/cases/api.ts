import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";

/** Etapa del expediente, tal como la publica el backend en `/cases/stages`. */
export interface StageInfo {
  code: string;
  label: string;
  is_initial: boolean;
  substatuses: string[];
  allowed_next: string[];
}

export interface Case {
  id: string;
  case_number: string;
  source: string;
  stage_code: string;
  /** Etiqueta en español. Viene del backend para no repetir el diccionario aquí. */
  stage_label: string;
  substatus_code: string | null;
  stage_reason: string | null;
  customer_id: string | null;
  program_id: string | null;
  assigned_salesperson_id: string | null;
  assigned_admin_id: string | null;
  address_street: string | null;
  address_unit: string | null;
  address_city: string | null;
  address_state: string | null;
  address_zip: string | null;
  application_number: string | null;
  approval_code: string | null;
  funder_status_code: string | null;
  first_contact_at: string | null;
  submitted_at: string | null;
  approved_at: string | null;
  completed_at: string | null;
  closed_at: string | null;
  scheduled_install_date: string | null;
  created_at: string;
}

/** El mapa del flujo. Lo publica el backend para no duplicar los códigos aquí. */
export async function listStages(): Promise<StageInfo[]> {
  const res = await apiClient.get<{ stages: StageInfo[] }>("/cases/stages");
  return res.data.stages;
}

export async function listCasesPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Case>> {
  return fetchPage<Case>("/cases", page, pageSize, extraParams);
}
