import type { ReactNode } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import { NoAccess } from "@/components/NoAccess";

/**
 * Guarda de ruta por módulo o por permiso puntual.
 *
 * No monta los hijos cuando no hay acceso: si solo se escondiera la pantalla,
 * los componentes igual se montarían y dispararían sus consultas, que el
 * backend rechazaría con 403 una por una. Así no se pide nada.
 */
export function RequireAccess({
  children,
  module,
  permission,
  moduleLabel,
}: {
  children: ReactNode;
  module?: string;
  permission?: string;
  moduleLabel?: string;
}) {
  const { user, hasModule, hasPermission } = useAuth();

  if (!user) return null; // `ProtectedRoute` ya redirige al login.

  const allowed =
    (permission ? hasPermission(permission) : false) || (module ? hasModule(module) : false);

  if (!allowed) return <NoAccess moduleLabel={moduleLabel} />;
  return <>{children}</>;
}
