import { Fragment, useState, type ButtonHTMLAttributes, type ReactNode } from "react";
import { PaginationControls } from "@/components/PaginationControls";
import { SkeletonRows } from "@/components/ui/Skeleton";

/**
 * La tabla común del CRM. Todas las tablas usan este componente (o
 * `PaginatedTable`, abajo) para verse y comportarse igual: mismo encabezado,
 * misma fila, acciones con `RowActions`, filas que se despliegan con
 * `ExpandToggle` y, en el celular, una tarjeta por fila (`.is-cards`).
 *
 * - Un listado que viene del servidor va con `PaginatedTable`: recibe el
 *   resultado de `usePaginatedQuery` y pinta la paginación él mismo, así que
 *   no se puede olvidar (QA de José, 31 oct).
 * - `DataTable` solo es para listas cortas y acotadas que ya vienen completas
 *   (los equipos de una obra, los renglones de una cotización).
 */

/** Lo que cada celda recibe además de la fila: si está desplegada y cómo cambiarla. */
export interface RowContext {
  expanded: boolean;
  toggle: () => void;
}

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T, ctx: RowContext) => ReactNode;
  /** Clase extra de la celda; `is-hide-mobile` la quita de la tarjeta del celular
   * cuando su dato ya va en el título (propuesta UI/UX V1). */
  className?: string;
}

export interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  isLoading: boolean;
  emptyMessage?: string;
  getRowKey: (row: T) => string;
  /** Fila extra a todo el ancho bajo cada fila (detalle fijo). Si devuelve
   * `null`, esa fila no lleva detalle. */
  renderDetailRow?: (row: T) => ReactNode;
  /** Detalle que se abre y cierra con `ExpandToggle` (renglones de una salida o una lista). */
  expandable?: { render: (row: T) => ReactNode; defaultExpanded?: (row: T) => boolean };
  /** Clase de la fila, para marcas como «pendiente» (`fin-overdue`). */
  rowClassName?: (row: T) => string | undefined;
  /** Clase extra de la tabla, para ajustes de una pantalla. */
  className?: string;
  /** Agrupa filas seguidas con el mismo valor bajo un subtítulo (la sección de un renglón). */
  groupBy?: (row: T) => string | null | undefined;
  /** Fila de totales al final: una celda por columna, en el mismo orden. */
  footer?: ReactNode[];
}

export function DataTable<T>({
  columns,
  rows,
  isLoading,
  emptyMessage = "Sin resultados para mostrar.",
  getRowKey,
  renderDetailRow,
  expandable,
  rowClassName,
  className,
  groupBy,
  footer,
}: DataTableProps<T>) {
  const [abiertas, setAbiertas] = useState<Record<string, boolean>>({});
  if (isLoading) return <SkeletonRows rows={5} />;
  // Sin filas, solo el mensaje: una tabla vacía en el celular quedaba como una tarjeta hueca.
  if (rows.length === 0) return <p className="acta-empty table-empty">{emptyMessage}</p>;

  function cellValue(row: T, key: string): ReactNode {
    const value = (row as Record<string, unknown>)[key];
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  return (
    <div className="table-wrap">
      {/* En el celular cada fila se vuelve una tarjeta (`.is-cards`, index.css):
          la tabla no cabía y se salía por la derecha (revisión del 17 oct). */}
      <table className={["data-table is-cards", className].filter(Boolean).join(" ")}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, n) => {
            const clave = getRowKey(row);
            const grupo = groupBy?.(row) || "";
            const nuevoGrupo = Boolean(grupo) && grupo !== (n > 0 ? groupBy?.(rows[n - 1]) || "" : "");
            const expanded = abiertas[clave] ?? expandable?.defaultExpanded?.(row) ?? false;
            const ctx: RowContext = { expanded, toggle: () => setAbiertas((a) => ({ ...a, [clave]: !expanded })) };
            const detalleFijo = renderDetailRow?.(row);
            return (
              <Fragment key={clave}>
                {nuevoGrupo && (
                  <tr className="is-group"><th colSpan={columns.length} scope="colgroup">{grupo}</th></tr>
                )}
                <tr className={[rowClassName?.(row), expanded ? "is-expanded" : ""].filter(Boolean).join(" ") || undefined}>
                  {columns.map((col, i) => (
                    <td key={col.key} data-label={col.header}
                      className={[i === 0 ? "is-title" : col.header === "" ? "is-actions" : "", col.className ?? ""]
                        .filter(Boolean).join(" ") || undefined}>
                      {col.render ? col.render(row, ctx) : cellValue(row, col.key)}
                    </td>
                  ))}
                </tr>
                {detalleFijo != null && detalleFijo !== false && (
                  <tr className="is-detail">
                    <td colSpan={columns.length}>{detalleFijo}</td>
                  </tr>
                )}
                {expandable && expanded && (
                  <tr className="is-detail is-expanded-detail">
                    <td colSpan={columns.length}>{expandable.render(row)}</td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
        {footer && (
          <tfoot>
            <tr className="is-total">
              {columns.map((col, i) => (
                <td key={col.key} data-label={col.header} className={i === 0 ? "is-title" : col.className}>{footer[i]}</td>
              ))}
            </tr>
          </tfoot>
        )}
      </table>
    </div>
  );
}

/** Lo que devuelve `usePaginatedQuery`: filas, carga y controles de página. */
export interface PaginatedList<T> {
  items: T[];
  isLoading: boolean;
  controls: { page: number; pageSize: number; total: number; onPageChange: (page: number) => void };
}

/**
 * Un listado del servidor: la tabla común con su paginación. Recibe el
 * resultado de `usePaginatedQuery` entero, así las filas y los controles de
 * página siempre salen de la misma consulta.
 *
 *   const lista = usePaginatedQuery<Salida>({ key, path: "/warehouse/releases" });
 *   <PaginatedTable list={lista} columns={columnas} getRowKey={(s) => s.id} />
 */
export function PaginatedTable<T>({ list, ...props }: Omit<DataTableProps<T>, "rows" | "isLoading"> & {
  list: PaginatedList<T>;
}) {
  return (
    <>
      <DataTable {...props} rows={list.items} isLoading={list.isLoading} />
      <PaginationControls {...list.controls} />
    </>
  );
}

/** Las acciones de una fila: la principal como botón, las demás como enlaces, separadas. */
export function RowActions({ children }: { children: ReactNode }) {
  return <div className="row-actions">{children}</div>;
}

/** Una acción de fila. `primary`: botón (Autorizar, Entregar); `link`: enlace (Editar, Ver); `danger`: enlace rojo (Borrar, Anular). */
export function RowAction({ variant = "link", className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "link" | "danger";
}) {
  const clase = variant === "primary" ? "acta-btn is-small is-primary" : variant === "danger" ? "acta-link is-danger" : "acta-link";
  return <button type="button" {...props} className={[clase, className].filter(Boolean).join(" ")} />;
}

/** El botón estándar para desplegar el detalle de una fila («Ver 46 renglones ▾»). */
export function ExpandToggle({ expanded, onToggle, children }: { expanded: boolean; onToggle: () => void; children: ReactNode }) {
  return (
    <button type="button" className="row-expand" aria-expanded={expanded} onClick={onToggle}>
      {expanded ? "Ocultar" : "Ver"} {children}<span aria-hidden="true">{expanded ? "▴" : "▾"}</span>
    </button>
  );
}
