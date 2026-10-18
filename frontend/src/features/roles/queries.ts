import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createRole, deleteRole, listPermissionCatalog, listRoles, updateRole } from "./api";

/**
 * Claves de consulta centralizadas: si cada componente las escribiera a mano,
 * una diferencia de texto haría que la lista no se refresque tras guardar.
 */
export const rolesKeys = {
  all: ["roles"] as const,
  catalog: ["permission-catalog"] as const,
};

export function usePermissionCatalog() {
  return useQuery({
    queryKey: rolesKeys.catalog,
    queryFn: listPermissionCatalog,
    // El catálogo cambia con un despliegue, no durante la sesión.
    staleTime: 5 * 60 * 1000,
  });
}

export function useRoles() {
  return useQuery({ queryKey: rolesKeys.all, queryFn: listRoles });
}

export function useCreateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createRole,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
    meta: { successMessage: "Rol creado." },
  });
}

export function useUpdateRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ code, ...payload }: { code: string; name?: string; permissions?: string[] }) =>
      updateRole(code, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
  });
}

export function useDeleteRole() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteRole,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: rolesKeys.all }),
    meta: { successMessage: "Rol eliminado." },
  });
}
