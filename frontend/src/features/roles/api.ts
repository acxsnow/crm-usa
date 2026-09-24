import { apiClient } from "@/lib/apiClient";
import type { PermissionCatalog, Role } from "@/types/users";

export async function listPermissionCatalog(): Promise<PermissionCatalog> {
  const res = await apiClient.get<PermissionCatalog>("/permissions");
  return res.data;
}

export async function listRoles(): Promise<Role[]> {
  const res = await apiClient.get<Role[]>("/roles");
  return res.data;
}

export async function createRole(payload: {
  code: string;
  name: string;
  permissions: string[];
}): Promise<Role> {
  const res = await apiClient.post<Role>("/roles", payload);
  return res.data;
}

export async function updateRole(
  code: string,
  payload: { name?: string; permissions?: string[] }
): Promise<Role> {
  const res = await apiClient.patch<Role>(`/roles/${code}`, payload);
  return res.data;
}

export async function deleteRole(code: string): Promise<void> {
  await apiClient.delete(`/roles/${code}`);
}
