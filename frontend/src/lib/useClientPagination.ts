import { useEffect, useState } from "react";

/**
 * Paginación para listas que el servidor ya entrega calculadas completas (un
 * reporte: compras sugeridas, nómina del periodo). Devuelve lo mismo que
 * `usePaginatedQuery`, así la pantalla usa `PaginatedTable` igual que con un
 * listado del servidor. Los totales se calculan sobre la lista completa, no
 * sobre la página.
 *
 *   const lista = useClientPagination(data?.rows, isLoading);
 *   <PaginatedTable list={lista} ... />
 */
export function useClientPagination<T>(rows: T[] | undefined, isLoading: boolean, pageSize = 25) {
  const [page, setPage] = useState(1);
  const total = rows?.length ?? 0;
  // Si la lista se acorta (un filtro), no quedarse en una página que ya no existe.
  useEffect(() => {
    const ultima = Math.max(1, Math.ceil(total / pageSize));
    if (page > ultima) setPage(ultima);
  }, [total, pageSize, page]);
  return {
    items: (rows ?? []).slice((page - 1) * pageSize, page * pageSize),
    total,
    page,
    setPage,
    isLoading,
    controls: { page, pageSize, total, onPageChange: setPage },
  };
}
