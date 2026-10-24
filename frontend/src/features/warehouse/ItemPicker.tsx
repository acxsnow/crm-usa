import { useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { SearchPicker } from "@/components/SearchPicker";
import { getItem, listItemsPage, warehouseKeys, type WarehouseItem } from "./api";

/** Cuántos artículos trae cada búsqueda. */
const POR_BUSQUEDA = 20;

/** Clave de caché de un artículo por id; la comparten el buscador y `useWarehouseItems`.
 * Empieza por `warehouseKeys.items`: lo que invalida el catálogo (una entrega,
 * una jornada) también refresca las existencias de lo ya elegido. */
export const itemKey = (id: string) => [...warehouseKeys.items, "uno", id] as const;

/**
 * Los artículos de una lista de ids, para los renglones que ya traen un
 * artículo elegido (al editar) y necesitan su unidad, costo o existencias.
 * Lo que se eligió con el buscador ya está en caché y no se vuelve a pedir.
 */
export function useWarehouseItems(ids: string[]): Record<string, WarehouseItem> {
  const unicos = [...new Set(ids.filter(Boolean))];
  const resultados = useQueries({
    queries: unicos.map((id) => ({ queryKey: itemKey(id), queryFn: () => getItem(id), staleTime: 60_000 })),
  });
  const porId: Record<string, WarehouseItem> = {};
  resultados.forEach((r) => { if (r.data) porId[r.data.id] = r.data; });
  return porId;
}

/**
 * Buscador de artículos activos del catálogo de bodega, por nombre, referencia
 * o proveedor (`GET /warehouse/items?q=`). Recibe el id elegido y devuelve el
 * artículo completo, para que quien lo usa tome su unidad, costo o existencias.
 */
export function ItemPicker({ itemId, onChange, label, clearLabel, disabled }: {
  itemId: string;
  onChange: (item: WarehouseItem | null) => void;
  label: string;
  /** Si se da, el campo se puede dejar sin artículo. */
  clearLabel?: string;
  disabled?: boolean;
}) {
  const queryClient = useQueryClient();
  const { data: elegido, isLoading } = useQuery({
    queryKey: itemKey(itemId),
    queryFn: () => getItem(itemId),
    enabled: Boolean(itemId),
    staleTime: 60_000,
  });

  return (
    <SearchPicker<WarehouseItem>
      label={label}
      value={itemId ? elegido ?? null : null}
      onChange={(item) => {
        if (item) queryClient.setQueryData(itemKey(item.id), item);
        onChange(item);
      }}
      search={(q) => listItemsPage(1, POR_BUSQUEDA, { active: true, q: q || undefined }).then((p) => p.items)}
      queryKey={[...warehouseKeys.items, "buscador"]}
      getKey={(a) => a.id}
      getLabel={(a) => (a.sku ? `${a.name} (${a.sku})` : a.name)}
      renderOption={(a) => (
        <>
          <strong>{a.name}</strong>
          <small>{[a.sku, a.category_label, a.unit_label].filter(Boolean).join(" · ")}</small>
        </>
      )}
      pageSize={POR_BUSQUEDA}
      placeholder="Busca por nombre o referencia"
      pendingLabel={itemId && isLoading ? "Cargando…" : undefined}
      clearLabel={clearLabel}
      disabled={disabled}
    />
  );
}
