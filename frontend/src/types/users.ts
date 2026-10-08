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

/** Ficha de solo lectura de una persona del equipo. */
export interface UserProfile {
  id: string;
  email: string;
  full_name: string;
  status: UserStatus;
  roles: string[];
  role_names: string[];
  /** Cuándo se le envió la invitación y quién. */
  invited_at: string;
  invited_by: string | null;
  /** Cuándo aceptó la invitación y creó su clave. */
  joined_at: string | null;
  /** Falso si se creó sin invitación (carga inicial o alta directa). */
  has_invitation: boolean;
  last_login_at: string | null;
  /** Programas y zonas de venta. `null` si quien consulta no puede ver programas. */
  zones: { program_code: string; program_name: string; zone_name: string; city: string | null; state: string | null; active: boolean }[] | null;
}
