import { useEffect, useState } from "react";
import { keepPreviousData, useQuery, type QueryKey } from "@tanstack/react-query";
import { fetchPage, type Page } from "./pagination";

/**
 * Gancho común para cualquier listado paginado del backend
 * (`app/shared/pagination.py`: limit/offset, total en X-Total-Count).
 *
 * Maneja la página actual, pide solo esa página y devuelve lo que necesita
 * `PaginationControls`. Si cambian los filtros (`params`), vuelve a la página 1.
 * Toda tabla o lista nueva debería usarlo en vez de pedir el listado completo.
 *
 *   const lista = usePaginatedQuery<Producto>({ key: ["products"], path: "/products", pageSize: 20 });
 *   lista.items.map(...)
 *   <PaginationControls {...lista.controls} />
 */
export function usePaginatedQuery<T>({ key, path, pageSize = 20, params = {}, enabled = true, refetchInterval = false }: {
  /** Prefijo de la clave de react-query: invalidarlo refresca todas las páginas. */
  key: QueryKey;
  path: string;
  pageSize?: number;
  /** Filtros que se mandan al backend; al cambiar, se vuelve a la primera página. */
  params?: Record<string, string | number | boolean | undefined>;
  enabled?: boolean;
  /** Volver a pedir la página cada tantos ms (por ejemplo, mientras algo se envía). */
  refetchInterval?: number | false;
}) {
  const [page, setPage] = useState(1);
  const firma = JSON.stringify(params);
  useEffect(() => { setPage(1); }, [firma]);

  const query = useQuery<Page<T>>({
    queryKey: [...key, "page", page, pageSize, params],
    queryFn: () => fetchPage<T>(path, page, pageSize, params),
    placeholderData: keepPreviousData,
    enabled,
    refetchInterval,
  });

  const total = query.data?.total ?? 0;
  return {
    items: query.data?.items ?? [],
    total,
    page,
    setPage,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    /** Props listos para `<PaginationControls {...controls} />`. */
    controls: { page, pageSize, total, onPageChange: setPage },
  };
}
