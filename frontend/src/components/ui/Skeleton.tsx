/** Bloque gris animado mientras algo carga (sin animación si se pide menos movimiento). */
export function Skeleton({ width = "100%", height = 14, label }: {
  width?: number | string;
  height?: number | string;
  label?: string;
}) {
  return (
    <span className="ui-skeleton" style={{ width, height }}
      {...(label ? { role: "status", "aria-label": label } : { "aria-hidden": true })} />
  );
}

/** Varias filas de esqueleto, para listas y tablas que cargan. */
export function SkeletonRows({ rows = 4, label = "Cargando…" }: { rows?: number; label?: string }) {
  return (
    <div className="ui-skeleton-rows" role="status" aria-label={label}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} height={18} width={i % 2 ? "88%" : "100%"} />
      ))}
    </div>
  );
}
