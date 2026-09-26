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
  /** Viene con el sistema (no se puede borrar) o lo creó la organización. */
  is_system: boolean;
  /** Bloqueado: ni se edita ni se borra. Solo el rol de Administrador. */
  is_locked: boolean;
  permissions: string[];
  user_count: number;
}

export interface Permission {
  code: string;
  description: string;
}

/** Grupo de permisos; es la unidad que enciende un ítem del menú. */
export interface PermissionModule {
  key: string;
  label: string;
  permissions: string[];
}

export interface PermissionCatalog {
  modules: PermissionModule[];
  permissions: Permission[];
}
