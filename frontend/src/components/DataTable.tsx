import { Fragment, type ReactNode } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  isLoading: boolean;
  emptyMessage?: string;
  getRowKey: (row: T) => string;
  /** Optional extra row rendered right after each data row, spanning all
   * columns — for inline detail/expansion content (e.g. attachments and a
   * payment form under an invoice) that doesn't fit a single table cell. */
  renderDetailRow?: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  isLoading,
  emptyMessage = "Sin resultados para mostrar.",
  getRowKey,
  renderDetailRow,
}: DataTableProps<T>) {
  if (isLoading) return <p>Cargando...</p>;

  function cellValue(row: T, key: string): ReactNode {
    const value = (row as Record<string, unknown>)[key];
    return value === null || value === undefined || value === "" ? "—" : String(value);
  }

  return (
    <div className="table-wrap">
      {/* En el celular cada fila se vuelve una tarjeta (`.is-cards`, index.css):
          la tabla no cabía y se salía por la derecha (revisión del 17 oct). */}
      <table className="data-table is-cards">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <Fragment key={getRowKey(row)}>
              <tr>
                {columns.map((col, i) => (
                  <td key={col.key} data-label={col.header}
                    className={i === 0 ? "is-title" : col.header === "" ? "is-actions" : undefined}>
                    {col.render ? col.render(row) : cellValue(row, col.key)}
                  </td>
                ))}
              </tr>
              {renderDetailRow && (
                <tr>
                  <td colSpan={columns.length}>{renderDetailRow(row)}</td>
                </tr>
              )}
            </Fragment>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="page-subtitle">
                {emptyMessage}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
