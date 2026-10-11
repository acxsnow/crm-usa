import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/features/auth/AuthContext";
import { hasAnyPermission } from "@/config/navigation";

/**
 * Guarda de ruta por permiso.
 *
 * Quien escribe en la barra la dirección de una sección que su rol no tiene
 * vuelve al inicio, sin pantalla intermedia (antes veía «No tienes acceso»).
 * No monta los hijos: si solo se escondiera la pantalla, los componentes igual
 * se montarían y dispararían sus consultas, que el backend rechazaría con 403.
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
}: {
  children: ReactNode;
  permission: string | string[];
  /** Nombre de la sección; queda como documentación en `router.tsx`. */
  moduleLabel?: string;
}) {
  const { user } = useAuth();

  if (!user) return null; // `ProtectedRoute` ya redirige al login.
  if (!hasAnyPermission(permission, user)) return <Navigate to="/" replace />;
  return <>{children}</>;
}
