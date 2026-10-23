interface Props {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function PaginationControls({ page, pageSize, total, onPageChange }: Props) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  if (total <= pageSize && page === 1) return null;

  return (
    <div className="inline-form ui-pagination" style={{ marginTop: "0.75rem" }}>
      <button type="button" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
        Anterior
      </button>
      <span className="page-subtitle">
        {from}–{to} de {total}
      </span>
      <button type="button" disabled={page >= lastPage} onClick={() => onPageChange(page + 1)}>
        Siguiente
      </button>
    </div>
  );
}
