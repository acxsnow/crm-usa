import { apiClient } from "@/lib/apiClient";
import type { OrgUser, Role, UserListResponse, UserProfile } from "@/types/users";

export async function listUsers(): Promise<UserListResponse> {
  const res = await apiClient.get<UserListResponse>("/users");
  return res.data;
}

export async function listUsersPage(
  page: number,
  pageSize: number,
  extraParams: Record<string, string> = {}
): Promise<UserListResponse> {
  const res = await apiClient.get<UserListResponse>("/users", {
    params: { ...extraParams, limit: pageSize, offset: (page - 1) * pageSize },
  });
  return res.data;
}

export async function inviteUser(payload: { email: string; full_name: string; role_codes: string[] }): Promise<OrgUser> {
  const res = await apiClient.post<OrgUser>("/users", payload);
  return res.data;
}

export async function activateUser(userId: string): Promise<OrgUser> {
  const res = await apiClient.post<OrgUser>(`/users/${userId}/activate`, {});
  return res.data;
}

export async function deactivateUser(userId: string): Promise<OrgUser> {
  const res = await apiClient.post<OrgUser>(`/users/${userId}/deactivate`, {});
  return res.data;
}

export async function listRoles(): Promise<Role[]> {
  const res = await apiClient.get<Role[]>("/roles");
  return res.data;
}

export async function updateUserRoles(userId: string, roleCodes: string[]): Promise<OrgUser> {
  const res = await apiClient.patch<OrgUser>(`/users/${userId}/roles`, { role_codes: roleCodes });
  return res.data;
}

export async function updateUser(userId: string, fullName: string): Promise<OrgUser> {
  const res = await apiClient.patch<OrgUser>(`/users/${userId}`, { full_name: fullName });
  return res.data;
}

export async function getUserProfile(userId: string): Promise<UserProfile> {
  const res = await apiClient.get<UserProfile>(`/users/${userId}/profile`);
  return res.data;
}
