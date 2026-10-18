import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateUser, updateUserRoles } from "./api";

/** Clave de la lista de usuarios; centralizada para que las mutaciones la refresquen. */
export const usersKeys = { all: ["users"] as const };

export function useUpdateUserRoles() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, roleCodes }: { userId: string; roleCodes: string[] }) =>
      updateUserRoles(userId, roleCodes),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usersKeys.all }),
    meta: { silent: true },  // UserEditPanel avisa una vez al terminar
  });
}

export function useUpdateUser() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, fullName }: { userId: string; fullName: string }) =>
      updateUser(userId, fullName),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: usersKeys.all }),
    meta: { silent: true },  // UserEditPanel avisa una vez al terminar
  });
}
