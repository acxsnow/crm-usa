import type { Address } from "./crm";

export type ProjectStatus = "planning" | "scheduled" | "in_progress" | "completed" | "cancelled";

export interface Project extends Address {
  id: string;
  customer_id: string;
  opportunity_id?: string | null;
  title: string;
  project_type?: string | null;
  status: ProjectStatus;
  scheduled_date?: string | null;
  completed_date?: string | null;
  primary_technician_user_id?: string | null;
  notes?: string | null;
  created_at: string;
}

export interface ChecklistTemplateItem {
  id: string;
  label: string;
  sort_order: number;
  is_required: boolean;
  requires_evidence: boolean;
}

export interface ChecklistTemplate {
  id: string;
  name: string;
  project_type?: string | null;
  items: ChecklistTemplateItem[];
}

export interface ProjectChecklistItem {
  id: string;
  label: string;
  sort_order: number;
  is_required: boolean;
  requires_evidence: boolean;
  is_complete: boolean;
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

export type EvidenceCategory = "before" | "during" | "after" | "damage" | "other";

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
