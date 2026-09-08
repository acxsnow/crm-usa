export type UserStatus = "active" | "inactive" | "invited";

export interface OrgUser {
  id: string;
  email: string;
  full_name: string;
  status: UserStatus;
  roles: string[];
  last_login_at?: string | null;
}

export interface UserListResponse {
  items: OrgUser[];
  total: number;
  active_user_count: number;
  max_active_users: number;
}

export interface Role {
  code: string;
  name: string;
  permissions: string[];
}
