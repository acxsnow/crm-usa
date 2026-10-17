import type { Address } from "./crm";

export type ProjectStatus = "planning" | "scheduled" | "in_progress" | "completed" | "cancelled";

export const PROJECT_STATUS_LABELS: Record<ProjectStatus, string> = {
  planning: "Por agendar",
  scheduled: "Agendado",
  in_progress: "En curso",
  completed: "Cerrado",
  cancelled: "Cancelado",
};

export interface Project extends Address {
  id: string;
  customer_id: string;
  case_id?: string | null;
  title: string;
  project_type?: string | null;
  status: ProjectStatus;
  scheduled_date?: string | null;
  completed_date?: string | null;
  primary_technician_user_id?: string | null;
  notes?: string | null;
  installation_conditions: string[];
  /** Etapa del expediente del que nace el proyecto (solo lectura). */
  case_number?: string | null;
  case_stage_code?: string | null;
  case_stage_label?: string | null;
  case_substatus_code?: string | null;
  /** Administración confirmó la información técnica del acta (módulo 6). */
  technician_info_confirmed?: boolean;
  /** Motivo de la última devolución al técnico, si el acta está devuelta. */
  returned_reason?: string | null;
  created_at: string;
}

export interface ProjectReview {
  id: string;
  action: "confirmed" | "returned" | "reopened";
  reason: string | null;
  actor_user_id: string | null;
  created_at: string;
}

export interface ChecklistTemplateItem {
  id: string;
  label: string;
  sort_order: number;
  is_required: boolean;
  requires_evidence: boolean;
  section?: string | null;
  evidence_category?: string | null;
  condition_code?: string | null;
  allows_not_applicable?: boolean;
}

export interface ChecklistTemplate {
  id: string;
  name: string;
  project_type?: string | null;
  /** Nulo: la plantilla por defecto de la organización. */
  program_id?: string | null;
  items: ChecklistTemplateItem[];
}

export interface ProjectChecklistItem {
  id: string;
  label: string;
  sort_order: number;
  is_required: boolean;
  requires_evidence: boolean;
  section: string | null;
  evidence_category: string | null;
  condition_code: string | null;
  allows_not_applicable: boolean;
  is_complete: boolean;
  not_applicable: boolean;
  not_applicable_reason: string | null;
  completed_at?: string | null;
  completed_by_user_id?: string | null;
}

export type TaskStatus = "pending" | "in_progress" | "done";

export interface FieldTask {
  id: string;
  project_id: string;
  title: string;
  description?: string | null;
  status: TaskStatus;
  assigned_user_id?: string | null;
  due_date?: string | null;
  completed_at?: string | null;
  is_overdue: boolean;
  created_at: string;
}

export interface TaskComment {
  id: string;
  task_id: string;
  author_user_id: string;
  body: string;
  created_at: string;
}

/** Código del catálogo de evidencias (15 categorías, `GET /field-ops/catalogs`). */
export type EvidenceCategory = string;

export interface Evidence {
  id: string;
  project_id: string;
  task_id?: string | null;
  checklist_item_id?: string | null;
  category: EvidenceCategory;
  original_filename?: string | null;
  mime_type?: string | null;
  size_bytes?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  captured_at?: string | null;
  watermarked: boolean;
  uploaded_by_user_id: string;
  created_at: string;
}

export interface Attestation {
  id: string;
  project_id: string;
  technician_user_id?: string | null;
  technician_signed_at?: string | null;
  customer_name?: string | null;
  customer_signed_at?: string | null;
  pdf_path?: string | null;
  generated_at?: string | null;
  is_fully_signed: boolean;
}

// --- Módulo 5 ---------------------------------------------------------------

/** Catálogos con etiquetas en español; el backend es la única fuente. */
export interface FieldCatalogs {
  evidence_categories: Record<string, string>;
  installation_conditions: Record<string, string>;
  equipment_types: Record<string, string>;
  permit_statuses: Record<string, string>;
  inspection_results: Record<string, string>;
}

export type PermitStatus = "submitted" | "approved" | "rejected" | "not_required";

export interface Permit {
  id: string;
  project_id: string;
  jurisdiction: string;
  permit_number: string | null;
  permit_type: string | null;
  status: PermitStatus;
  filed_on: string | null;
  approved_on: string | null;
  expires_on: string | null;
  not_required_reason: string | null;
  notes: string | null;
  is_expired: boolean;
  is_cleared: boolean;
  /** Si deja pasar a «Listo para instalar» (con PERMIT_FILED_ALLOWS_INSTALL, también radicado). */
  allows_install: boolean;
  created_at: string;
}

export type InspectionResult = "pending" | "passed" | "failed";

export interface Inspection {
  id: string;
  project_id: string;
  scheduled_for: string;
  inspector_name: string | null;
  result: InspectionResult;
  result_recorded_at: string | null;
  observations: string | null;
  created_at: string;
}

export interface InstalledEquipment {
  id: string;
  project_id: string;
  equipment_type: string;
  brand: string;
  model: string;
  serial_number: string | null;
  quantity: number;
  unit_label: string | null;
  notes: string | null;
  created_at: string;
}

export interface ProjectMaterial {
  id: string;
  project_id: string;
  description: string;
  sku: string | null;
  quantity: number;
  unit: string | null;
  notes: string | null;
}

export interface InstallationGaps {
  can_close: boolean;
  missing: string[];
}

export interface AgendaRow {
  project_id: string;
  title: string;
  status: ProjectStatus;
  scheduled_date: string | null;
  primary_technician_user_id: string | null;
  address_street: string | null;
  address_unit: string | null;
  address_city: string | null;
  case_id: string | null;
  case_number: string | null;
  stage_code: string | null;
  substatus_code: string | null;
  /** Días de atraso si sigue sin cerrar y su fecha ya pasó (lo calcula el servidor). */
  days_late: number | null;
}
