/** API del módulo 2: el vendedor en la puerta. */
import { apiClient } from "@/lib/apiClient";
import type { Case } from "@/features/cases/api";
import type { DefinitionStep, Evaluation } from "@/types/programs";

export interface MyProgram {
  program: { id: string; code: string; name: string };
  version_id: string;
  version: string;
  zones: { id: string; code: string; name: string; state: string | null; city: string | null }[];
}

export interface CaseForm {
  case: Case;
  definition: { steps: DefinitionStep[]; version: string };
  answers: Record<string, unknown>;
  saved_at: Record<string, string>;
  evaluation: Evaluation;
  files: { id: string; field_key: string; original_filename: string | null; mime_type: string | null; watermarked: boolean;
    review_status: "pending" | "accepted" | "rejected"; review_notes: string | null }[];
  terms: { id: string; version: string; language: string; title: string; body: string } | null;
  acceptance: { id: string; customer_name: string; accepted_at: string; terms_version: string | null } | null;
  editable: boolean;
}

export interface BoardColumn {
  code: string;
  label: string;
  count: number;
  cases: { id: string; case_number: string; customer_name: string | null; address: string;
    program_name: string | null; substatus_code: string | null; updated_at: string | null }[];
}

export const salesKeys = {
  mine: ["me-programs"] as const,
  form: (id: string) => ["case-form", id] as const,
  board: (early: boolean, mine = false) => ["case-board", early, mine] as const,
};

export const VISIT_RESULTS = [
  { value: "opened", label: "Abrió y sigue", hint: "Llenamos su solicitud" },
  { value: "no_contact", label: "No abrió", hint: "Volver otro día" },
  { value: "not_interested", label: "No le interesa", hint: "" },
  { value: "not_eligible", label: "No califica", hint: "" },
] as const;

export const myPrograms = async () => (await apiClient.get<MyProgram[]>("/me/programs")).data;

export const recordVisit = async (body: Record<string, unknown>) =>
  (await apiClient.post<{ outcome: string; case: Case }>("/visits", body)).data;

export const setCaseProgram = async (caseId: string, programId: string, zoneId?: string) =>
  (await apiClient.put<Case>(`/cases/${caseId}/program`, { program_id: programId, zone_id: zoneId || undefined })).data;

export const getCaseForm = async (caseId: string) => (await apiClient.get<CaseForm>(`/cases/${caseId}/form`)).data;

export const saveStep = async (caseId: string, step: string, answers: Record<string, unknown>,
  coords?: { latitude: number; longitude: number } | null) =>
  (await apiClient.put<CaseForm>(`/cases/${caseId}/steps/${step}`, { answers, ...(coords ?? {}) })).data;

export async function uploadCaseFile(caseId: string, fieldKey: string, file: File,
  coords?: { latitude: number; longitude: number } | null): Promise<string> {
  const form = new FormData();
  form.append("field_key", fieldKey);
  form.append("file", file);
  form.append("captured_at", new Date().toISOString());
  if (coords) {
    form.append("latitude", String(coords.latitude));
    form.append("longitude", String(coords.longitude));
  }
  const r = await apiClient.post<{ id: string }>(`/cases/${caseId}/files`, form,
    { headers: { "Content-Type": "multipart/form-data" } });
  return r.data.id;
}

export async function openCaseFile(fileId: string) {
  const r = await apiClient.get(`/case-files/${fileId}`, { responseType: "blob" });
  const url = URL.createObjectURL(r.data);
  window.open(url, "_blank", "noopener");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export const acceptTerms = async (caseId: string, body: { customer_name: string; signature: string;
  latitude?: number; longitude?: number }) => (await apiClient.post<Case>(`/cases/${caseId}/terms-acceptance`, body)).data;

export const submitCase = async (caseId: string) => (await apiClient.post<Case>(`/cases/${caseId}/submit`)).data;

/** Filtros del tablero; se aplican en el servidor, también a los totales. */
export interface BoardFilters {
  q?: string;
  salesperson_id?: string;
  program_id?: string;
}

/** Columnas del tablero: el total de cada etapa y su primera página de `limit`. */
export const getBoard = async (early: boolean, mine = false, limit?: number, filtros: BoardFilters = {}) =>
  (await apiClient.get<BoardColumn[]>("/case-board",
    { params: { include_early_closes: early, mine, limit, ...filtros } })).data;

/** Una página de una sola columna, desde `offset`. */
export const getBoardColumn = async (stage: string, early: boolean, offset: number, limit: number,
                                     filtros: BoardFilters = {}) => {
  const columnas = (await apiClient.get<BoardColumn[]>("/case-board",
    { params: { include_early_closes: early, stage, offset, limit, ...filtros } })).data;
  return columnas[0]?.cases ?? [];
};

// ---------------------------------------------------------------------------
// Documentos (módulo 3) y revisión de Administración (módulo 4)
// ---------------------------------------------------------------------------

export interface CaseDocument {
  id: string; field_key: string; step_title: string; label: string; original_filename: string | null;
  mime_type: string | null; size_bytes: number | null; watermarked: boolean; latitude: number | null;
  longitude: number | null; captured_at: string | null; uploaded_at: string | null;
  review_status: "pending" | "accepted" | "rejected"; review_label: string; review_notes: string | null;
  reviewed_by: string | null; reviewed_at: string | null;
}

export interface QueueRow {
  case_id: string; case_number: string; customer_name: string | null; program_name: string | null;
  stage_label: string; substatus_code: string | null; submitted_at: string | null;
  pending: number; accepted: number; rejected: number;
}

export interface StageEvent {
  id: string; from_stage_code: string | null; to_stage_code: string; from_substatus_code: string | null;
  to_substatus_code: string | null; reason: string | null; actor_user_id: string | null; occurred_at: string;
  /** Etiquetas en español que manda el backend (QA-REG-08). */
  to_stage_label: string; to_substatus_label: string | null;
}

export const docKeys = {
  list: (caseId: string) => ["case-documents", caseId] as const,
  queue: ["document-queue"] as const,
  events: (caseId: string) => ["case-events", caseId] as const,
};

export const listDocuments = async (caseId: string) =>
  (await apiClient.get<CaseDocument[]>(`/cases/${caseId}/documents`)).data;

export const reviewDocument = async (fileId: string, status: "accepted" | "rejected", notes?: string) =>
  (await apiClient.post(`/case-files/${fileId}/review`, { status, notes: notes || undefined })).data;

export async function uploadExtraDocument(caseId: string, label: string, file: File) {
  const form = new FormData();
  form.append("label", label);
  form.append("file", file);
  return (await apiClient.post(`/cases/${caseId}/documents`, form, { headers: { "Content-Type": "multipart/form-data" } })).data;
}


export const caseEvents = async (caseId: string) =>
  (await apiClient.get<StageEvent[]>(`/cases/${caseId}/events`)).data;

export const transitionCase = async (caseId: string, body: { to_stage: string; reason?: string; substatus?: string;
  approval_code?: string; application_number?: string }) =>
  (await apiClient.post<Case>(`/cases/${caseId}/transition`, body)).data;

export const setSubstatus = async (caseId: string, substatus: string, reason?: string) =>
  (await apiClient.post<Case>(`/cases/${caseId}/substatus`, { substatus, reason: reason || undefined })).data;

/** Una imagen o PDF protegido como URL local (el archivo exige el token). */
export async function fileBlobUrl(fileId: string): Promise<string> {
  const r = await apiClient.get(`/case-files/${fileId}`, { responseType: "blob" });
  return URL.createObjectURL(r.data);
}

// ---------------------------------------------------------------------------
// Expediente sin formulario y su proyecto
// ---------------------------------------------------------------------------

export interface ProgramOptions { assigned: boolean; options: MyProgram[] }
export const programOptions = async () => (await apiClient.get<ProgramOptions>("/me/program-options")).data;
export const getCase = async (caseId: string) => (await apiClient.get<Case>(`/cases/${caseId}`)).data;
export const caseProject = async (caseId: string) =>
  (await apiClient.get<{ id: string; title: string; status: string }>(`/cases/${caseId}/project`)).data;
/** El código de error de la API (p. ej. "program_required"), si lo hay. */
export const errorCode = (e: unknown) => (e as { response?: { data?: { code?: string } } })?.response?.data?.code;
