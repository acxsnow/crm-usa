/** API del módulo 1 (programas). Errores en español en `detail`. */
import { useQuery } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  Evaluation,
  FieldDefinition,
  Program,
  ProgramCatalogs,
  ProgramTerms,
  ProgramVersion,
  VersionDetail,
  Zone,
} from "@/types/programs";

export const programKeys = {
  list: ["programs"] as const,
  program: (id: string) => ["program", id] as const,
  part: (id: string, part: string) => ["program", id, part] as const,
  fields: ["program-fields"] as const,
  version: (id: string) => ["program-version", id] as const,
};

export function useProgramCatalogs() {
  return useQuery({
    queryKey: ["program-catalogs"],
    queryFn: async () => (await apiClient.get<ProgramCatalogs>("/programs/catalogs")).data,
    staleTime: Infinity,
  });
}

export const listPrograms = async () => (await apiClient.get<Program[]>("/programs")).data;
export const createProgram = async (body: Partial<Program>) => (await apiClient.post<Program>("/programs", body)).data;
export const updateProgram = async (id: string, body: Partial<Program>) =>
  (await apiClient.patch<Program>(`/programs/${id}`, body)).data;
export const installDefaults = async () =>
  (await apiClient.post<{ fields_created: number; programs_created: string[] }>("/programs/install-defaults")).data;

export const listTerms = async (id: string) => (await apiClient.get<ProgramTerms[]>(`/programs/${id}/terms`)).data;
export const createTerms = async (id: string, body: { version: string; language: string; title?: string; body: string }) =>
  (await apiClient.post<ProgramTerms>(`/programs/${id}/terms`, body)).data;
export const publishTerms = async (termsId: string) =>
  (await apiClient.post<ProgramTerms>(`/program-terms/${termsId}/publish`)).data;

export const listFields = async () => (await apiClient.get<FieldDefinition[]>("/fields")).data;
export const createField = async (body: Partial<FieldDefinition>) =>
  (await apiClient.post<FieldDefinition>("/fields", body)).data;
export const updateField = async (id: string, body: Partial<FieldDefinition>) =>
  (await apiClient.patch<FieldDefinition>(`/fields/${id}`, body)).data;

export const listVersions = async (id: string) =>
  (await apiClient.get<ProgramVersion[]>(`/programs/${id}/versions`)).data;
export const createVersion = async (id: string) =>
  (await apiClient.post<ProgramVersion>(`/programs/${id}/versions`)).data;
export const getVersion = async (id: string) => (await apiClient.get<VersionDetail>(`/program-versions/${id}`)).data;
export const updateVersion = async (id: string, body: { terms_id?: string | null; notes?: string }) =>
  (await apiClient.patch<ProgramVersion>(`/program-versions/${id}`, body)).data;
export const publishVersion = async (id: string) =>
  (await apiClient.post<ProgramVersion>(`/program-versions/${id}/publish`)).data;
export const previewVersion = async (id: string, answers: Record<string, unknown>, includeInternal = true) =>
  (await apiClient.post<Evaluation>(`/program-versions/${id}/preview`, { answers, include_internal: includeInternal })).data;

export const addStep = async (phaseId: string, body: { title: string; description?: string }) =>
  (await apiClient.post(`/workflow-phases/${phaseId}/steps`, body)).data;
export const updateStep = async (stepId: string, body: { title?: string; description?: string }) =>
  apiClient.patch(`/workflow-steps/${stepId}`, body);
export const deleteStep = async (stepId: string) => apiClient.delete(`/workflow-steps/${stepId}`);
export const moveStep = async (stepId: string, direction: "up" | "down") =>
  apiClient.post(`/workflow-steps/${stepId}/move`, { direction });
export const addStepField = async (stepId: string, body: { field_id: string; requirement: string;
  condition?: unknown; label_override?: string }) =>
  (await apiClient.post(`/workflow-steps/${stepId}/fields`, body)).data;
export const updateStepField = async (id: string, body: { requirement?: string; condition?: unknown;
  label_override?: string | null }) => apiClient.patch(`/workflow-step-fields/${id}`, body);
export const deleteStepField = async (id: string) => apiClient.delete(`/workflow-step-fields/${id}`);
export const moveStepField = async (id: string, direction: "up" | "down") =>
  apiClient.post(`/workflow-step-fields/${id}/move`, { direction });

export const listZones = async (id: string) => (await apiClient.get<Zone[]>(`/programs/${id}/zones`)).data;
export const createZone = async (id: string, body: { name: string; state?: string; city?: string }) =>
  (await apiClient.post<Zone>(`/programs/${id}/zones`, body)).data;
export const updateZone = async (id: string, body: Partial<Zone>) => (await apiClient.patch<Zone>(`/zones/${id}`, body)).data;
export const setZoneSalespeople = async (id: string, userIds: string[]) =>
  (await apiClient.put<string[]>(`/zones/${id}/salespeople`, { user_ids: userIds })).data;

export const VERSION_STATUS: Record<string, string> = { draft: "Borrador", published: "Publicada", archived: "Archivada" };
