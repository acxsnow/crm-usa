import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Skeleton } from "./Skeleton";

/**
 * Indicador del tablero: etiqueta, valor y una nota. Mientras carga muestra un
 * esqueleto en vez de «—». Con `to`, la tarjeta entera lleva al detalle.
 * Usa las clases `metric-card` de siempre, así se ve igual en toda la app.
 */
export function KpiCard({ label, value, note, icon, loading, to }: {
  label: string;
  value: ReactNode;
  note?: ReactNode;
  icon?: ReactNode;
  loading?: boolean;
  to?: string;
}) {
  const cuerpo = (
    <>
      <div className="ui-kpi-head">
        {icon && <span className="ui-kpi-icon" aria-hidden="true">{icon}</span>}
        <span>{label}</span>
      </div>
      {loading ? <Skeleton width="60%" height={30} label={`Cargando ${label}`} /> : <strong>{value}</strong>}
      {note && <small>{note}</small>}
    </>
  );
  return to
    ? <Link to={to} className="metric-card ui-kpi-card">{cuerpo}</Link>
    : <article className="metric-card ui-kpi-card">{cuerpo}</article>;
}
