import type { ReactNode } from "react";
import { MutationCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/features/auth/AuthContext";
import { Toaster } from "@/components/Toaster";
import { toast } from "@/lib/toast";

declare module "@tanstack/react-query" {
  interface Register {
    /**
     * `successMessage`: texto del aviso al guardar (por defecto «Cambios
     * guardados.»). `silent`: sin aviso, para lo que no es guardar (marcar como
     * leído, abrir una vista previa) o ya muestra su propio resultado.
     */
    mutationMeta: { successMessage?: string; silent?: boolean };
  }
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
  // Toda acción que guarda con éxito avisa, en un solo sitio para toda la app
  // (spec 2026-10-18-guardar-equipos-y-avisos). Los errores siguen en cada formulario.
  mutationCache: new MutationCache({
    onSuccess: (_data, _variables, _context, mutation) => {
      const meta = mutation.options.meta;
      if (!meta?.silent) toast(meta?.successMessage ?? "Cambios guardados.");
    },
  }),
});

export function AppProviders({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
      <Toaster />
    </QueryClientProvider>
  );
}
