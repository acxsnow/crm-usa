import { apiClient } from "@/lib/apiClient";
import { fetchPage, type Page } from "@/lib/pagination";
import type {
  Attestation,
  ChecklistTemplate,
  Evidence,
  FieldTask,
  Project,
  ProjectChecklistItem,
  TaskComment,
} from "@/types/fieldOps";

// --- Checklist templates ----------------------------------------------------

export async function seedDefaultChecklistTemplate(): Promise<ChecklistTemplate> {
  const res = await apiClient.post<ChecklistTemplate>("/checklist-templates/seed-default", {});
  return res.data;
}

export async function listChecklistTemplates(): Promise<ChecklistTemplate[]> {
  const res = await apiClient.get<ChecklistTemplate[]>("/checklist-templates");
  return res.data;
}

// --- Projects ----------------------------------------------------------

export async function listProjects(): Promise<Project[]> {
  const res = await apiClient.get<Project[]>("/projects");
  return res.data;
}

export async function listProjectsPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<Page<Project>> {
  return fetchPage<Project>("/projects", page, pageSize, extraParams);
}

export async function getProject(projectId: string): Promise<Project> {
  const res = await apiClient.get<Project>(`/projects/${projectId}`);
  return res.data;
}

export async function createProject(payload: Partial<Project> & { customer_id: string; title: string; apply_checklist_template_id?: string }): Promise<Project> {
  const res = await apiClient.post<Project>("/projects", payload);
  return res.data;
}

export async function updateProject(projectId: string, payload: Partial<Project>): Promise<Project> {
  const res = await apiClient.patch<Project>(`/projects/${projectId}`, payload);
  return res.data;
}

export async function getProjectChecklist(projectId: string): Promise<ProjectChecklistItem[]> {
  const res = await apiClient.get<ProjectChecklistItem[]>(`/projects/${projectId}/checklist`);
  return res.data;
}

export async function completeChecklistItem(itemId: string, isComplete: boolean): Promise<ProjectChecklistItem> {
  const res = await apiClient.patch<ProjectChecklistItem>(`/checklist-items/${itemId}`, { is_complete: isComplete });
  return res.data;
}

// --- Tasks ---------------------------------------------------------------

export async function listProjectTasks(projectId: string): Promise<FieldTask[]> {
  const res = await apiClient.get<FieldTask[]>(`/projects/${projectId}/tasks`);
  return res.data;
}

export async function createTask(
  projectId: string,
  payload: { title: string; description?: string; assigned_user_id?: string; due_date?: string }
): Promise<FieldTask> {
  const res = await apiClient.post<FieldTask>(`/projects/${projectId}/tasks`, payload);
  return res.data;
}

export async function listOverdueTasks(): Promise<(FieldTask & { project_title: string })[]> {
  const res = await apiClient.get<(FieldTask & { project_title: string })[]>("/tasks/overdue");
  return res.data;
}

export async function listTaskComments(taskId: string): Promise<TaskComment[]> {
  const res = await apiClient.get<TaskComment[]>(`/tasks/${taskId}/comments`);
  return res.data;
}

export async function createTaskComment(taskId: string, body: string): Promise<TaskComment> {
  const res = await apiClient.post<TaskComment>(`/tasks/${taskId}/comments`, { body });
  return res.data;
}

export async function updateTask(taskId: string, payload: Partial<FieldTask>): Promise<FieldTask> {
  const res = await apiClient.patch<FieldTask>(`/tasks/${taskId}`, payload);
  return res.data;
}

// --- Evidence ----------------------------------------------------------

export async function listProjectEvidencePage(projectId: string, page: number, pageSize: number): Promise<Page<Evidence>> {
  return fetchPage<Evidence>(`/projects/${projectId}/evidence`, page, pageSize);
}

export async function listProjectEvidence(projectId: string): Promise<Evidence[]> {
  const res = await apiClient.get<Evidence[]>(`/projects/${projectId}/evidence`);
  return res.data;
}

export async function uploadEvidence(
  projectId: string,
  file: File,
  options: { category: string; latitude?: number; longitude?: number; checklistItemId?: string }
): Promise<Evidence> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("category", options.category);
  if (options.latitude !== undefined) formData.append("latitude", String(options.latitude));
  if (options.longitude !== undefined) formData.append("longitude", String(options.longitude));
  if (options.checklistItemId) formData.append("checklist_item_id", options.checklistItemId);
  const res = await apiClient.post<Evidence>(`/projects/${projectId}/evidence`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function fetchEvidenceObjectUrl(evidenceId: string): Promise<string> {
  const res = await apiClient.get(`/evidence/${evidenceId}/file`, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}

// --- Attestation -----------------------------------------------------------

export async function getAttestation(projectId: string): Promise<Attestation | null> {
  try {
    const res = await apiClient.get<Attestation>(`/projects/${projectId}/attestation`);
    return res.data;
  } catch {
    return null;
  }
}

export async function signAsTechnician(projectId: string, signatureBase64: string): Promise<Attestation> {
  const res = await apiClient.post<Attestation>(`/projects/${projectId}/attestation/technician-sign`, {
    signature_base64: signatureBase64,
  });
  return res.data;
}

export async function signAsCustomer(projectId: string, customerName: string, signatureBase64: string): Promise<Attestation> {
  const res = await apiClient.post<Attestation>(`/projects/${projectId}/attestation/customer-sign`, {
    customer_name: customerName,
    signature_base64: signatureBase64,
  });
  return res.data;
}

export async function requestCustomerSignature(projectId: string): Promise<{ status: string; recipient_email: string; expires_at: string }> {
  const res = await apiClient.post(`/projects/${projectId}/attestation/customer-signature-request`, {});
  return res.data;
}

export interface PublicSignatureDetails {
  project_title: string;
  customer_name?: string | null;
  expires_at: string;
  technician_signed: boolean;
}

export async function getPublicSignatureDetails(token: string): Promise<PublicSignatureDetails> {
  const res = await apiClient.get<PublicSignatureDetails>("/public/customer-signature", { params: { token } });
  return res.data;
}

export async function submitPublicCustomerSignature(token: string, customerName: string, signatureBase64: string): Promise<Attestation> {
  const res = await apiClient.post<Attestation>("/public/customer-signature", { token, customer_name: customerName, signature_base64: signatureBase64 });
  return res.data;
}

export async function fetchAttestationPdfObjectUrl(attestationId: string): Promise<string> {
  const res = await apiClient.get(`/attestations/${attestationId}/pdf`, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}
