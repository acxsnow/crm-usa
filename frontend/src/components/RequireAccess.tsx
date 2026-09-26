import type { ReactNode } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import { NoAccess } from "@/components/NoAccess";
import { hasAnyPermission } from "@/config/navigation";

/**
 * Guarda de ruta por permiso.
 *
 * No monta los hijos cuando no hay acceso: si solo se escondiera la pantalla,
 * los componentes igual se montarían y dispararían sus consultas, que el
 * backend rechazaría con 403 una por una. Así no se pide nada.
 *
 * Deliberadamente **no** guarda por módulo. Un módulo se abre con cualquiera de
 * sus permisos, así que gatear una pantalla por módulo deja entrar a quien solo
 * comparte uno: al vendedor le bastaba `programs.read` para pasar la guarda de
 * la configuración de programas. Aquí se exige el permiso que la pantalla usa,
 * el mismo que el backend verifica con `require_permission`.
 *
 * Varios permisos se leen como "alguno de" — ver `config/navigation.ts`.
 */
export function RequireAccess({
  children,
  permission,
  moduleLabel,
}: {
  children: ReactNode;
  permission: string | string[];
  moduleLabel?: string;
}) {
  const { user } = useAuth();

  if (!user) return null; // `ProtectedRoute` ya redirige al login.
  if (!hasAnyPermission(permission, user)) return <NoAccess moduleLabel={moduleLabel} />;
  return <>{children}</>;
}
