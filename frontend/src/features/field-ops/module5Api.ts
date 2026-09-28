/**
 * API del módulo 5 (campo): condiciones, permisos, equipos, materiales,
 * inspecciones, agenda y cierre de instalación.
 *
 * Los mensajes de error vienen en español desde el backend (`detail`), así que
 * la pantalla los muestra tal cual con `apiErrorMessage`.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import type {
  AgendaRow,
  FieldCatalogs,
  Inspection,
  InstallationGaps,
  InstalledEquipment,
  Permit,
  Project,
  ProjectMaterial,
} from "@/types/fieldOps";

export function apiErrorMessage(err: unknown, fallback = "No se pudo completar la acción."): string {
  const detail = (err as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  return typeof detail === "string" ? detail : fallback;
}

/** Claves de consulta: invalidar una refresca todo lo que depende del proyecto. */
export const fieldKeys = {
  project: (id: string) => ["project", id] as const,
  checklist: (id: string) => ["project-checklist", id] as const,
  permits: (id: string) => ["project-permits", id] as const,
  equipment: (id: string) => ["project-equipment", id] as const,
  materials: (id: string) => ["project-materials", id] as const,
  inspections: (id: string) => ["project-inspections", id] as const,
  gaps: (id: string) => ["project-installation-gaps", id] as const,
};

// --- Catálogos -------------------------------------------------------------

export function useFieldCatalogs() {
  return useQuery({
    queryKey: ["field-catalogs"],
    queryFn: async () => (await apiClient.get<FieldCatalogs>("/field-ops/catalogs")).data,
    staleTime: Infinity, // cambian con un despliegue, no durante la sesión
  });
}

// --- Condiciones -------------------------------------------------------------

export async function setInstallationConditions(projectId: string, conditions: string[]): Promise<Project> {
  return (await apiClient.patch<Project>(`/projects/${projectId}/conditions`, { conditions })).data;
}

// --- Permisos municipales ------------------------------------------------------

export type PermitInput = Partial<Omit<Permit, "id" | "project_id" | "is_expired" | "is_cleared" | "created_at">> & {
  jurisdiction?: string;
};

export async function listPermits(projectId: string): Promise<Permit[]> {
  return (await apiClient.get<Permit[]>(`/projects/${projectId}/permits`)).data;
}

export async function recordPermit(projectId: string, input: PermitInput): Promise<Permit> {
  return (await apiClient.post<Permit>(`/projects/${projectId}/permits`, input)).data;
}

export async function updatePermit(permitId: string, input: PermitInput): Promise<Permit> {
  return (await apiClient.patch<Permit>(`/permits/${permitId}`, input)).data;
}

// --- Equipos y materiales -------------------------------------------------------

export type EquipmentInput = Omit<InstalledEquipment, "id" | "project_id" | "created_at">;

export async function listEquipment(projectId: string): Promise<InstalledEquipment[]> {
  return (await apiClient.get<InstalledEquipment[]>(`/projects/${projectId}/equipment`)).data;
}

export async function addEquipment(projectId: string, input: EquipmentInput): Promise<InstalledEquipment> {
  return (await apiClient.post<InstalledEquipment>(`/projects/${projectId}/equipment`, input)).data;
}

export async function deleteEquipment(equipmentId: string): Promise<void> {
  await apiClient.delete(`/equipment/${equipmentId}`);
}

export type MaterialInput = Omit<ProjectMaterial, "id" | "project_id">;

export async function listMaterials(projectId: string): Promise<ProjectMaterial[]> {
  return (await apiClient.get<ProjectMaterial[]>(`/projects/${projectId}/materials`)).data;
}

export async function addMaterial(projectId: string, input: MaterialInput): Promise<ProjectMaterial> {
  return (await apiClient.post<ProjectMaterial>(`/projects/${projectId}/materials`, input)).data;
}

export async function deleteMaterial(materialId: string): Promise<void> {
  await apiClient.delete(`/materials/${materialId}`);
}

// --- Inspecciones -------------------------------------------------------------

export async function listInspections(projectId: string): Promise<Inspection[]> {
  return (await apiClient.get<Inspection[]>(`/projects/${projectId}/inspections`)).data;
}

export async function scheduleInspection(
  projectId: string, input: { scheduled_for: string; inspector_name?: string }
): Promise<Inspection> {
  return (await apiClient.post<Inspection>(`/projects/${projectId}/inspections`, input)).data;
}

export async function recordInspectionResult(
  inspectionId: string, input: { result: "passed" | "failed"; observations?: string }
): Promise<Inspection> {
  return (await apiClient.post<Inspection>(`/inspections/${inspectionId}/result`, input)).data;
}

// --- Agenda y cierre --------------------------------------------------------------

export async function scheduleInstallation(
  projectId: string, input: { technician_user_id: string; scheduled_date: string }
): Promise<Project> {
  return (await apiClient.patch<Project>(`/projects/${projectId}/schedule`, input)).data;
}

export async function listAgenda(params: { date_from: string; date_to: string; technician_id?: string }): Promise<AgendaRow[]> {
  return (await apiClient.get<AgendaRow[]>("/dispatch/agenda", { params })).data;
}

export async function getInstallationGaps(projectId: string): Promise<InstallationGaps> {
  return (await apiClient.get<InstallationGaps>(`/projects/${projectId}/installation/gaps`)).data;
}

export async function closeInstallation(projectId: string, observations?: string): Promise<Project> {
  return (await apiClient.post<Project>(`/projects/${projectId}/installation/close`, { observations })).data;
}

/**
 * Un comando de campo puede cambiar varias cosas a la vez (cerrar la
 * instalación congela el checklist y cambia el estado del proyecto), así que
 * cada acción refresca todo lo que cuelga del proyecto.
 */
export function useRefreshProject(projectId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      [
        fieldKeys.project(projectId),
        fieldKeys.checklist(projectId),
        fieldKeys.permits(projectId),
        fieldKeys.equipment(projectId),
        fieldKeys.materials(projectId),
        fieldKeys.inspections(projectId),
        fieldKeys.gaps(projectId),
        ["project-evidence", projectId],
      ].map((queryKey) => queryClient.invalidateQueries({ queryKey })),
    );
}

/**
 * La fecha local del navegador en formato AAAA-MM-DD. `toISOString()` da la
 * fecha UTC: a partir de las 7 p. m. en Bogotá ya es "mañana" y la agenda
 * ofrecía como mínimo el día siguiente.
 */
export function localISODate(d: Date = new Date()): string {
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}
