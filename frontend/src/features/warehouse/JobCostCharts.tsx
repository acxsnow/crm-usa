/**
 * Las dos gráficas del costo del trabajo, en SVG propio (sin librería): la dona
 * del ingreso (ganancia contra costos) y la barra de en qué se fue el costo.
 */

export const CONCEPT_COLORS: Record<string, string> = {
  sales_rep: "#7b61ff",
  permits: "#e0a020",
  materials: "#1e88c8",
  labor: "#ef6c00",
  other: "#8a8f98",
};
const PROFIT_COLOR = "#2e9e4f";
const COST_COLOR = "#d81b60";

const RADIO = 15.9155; // circunferencia de 100: cada unidad es un punto porcentual

/** Dona del ingreso. Si la ganancia es negativa, todo el anillo es costo. */
export function RevenueDonut({ revenue, costs }: { revenue: number; costs: number }) {
  const costoPct = revenue > 0 ? Math.min(100, (costs / revenue) * 100) : 0;
  const gananciaPct = revenue > 0 ? Math.max(0, 100 - costoPct) : 0;
  return (
    <svg viewBox="0 0 42 42" className="jobcost-donut" role="img"
      aria-label={revenue > 0 ? `Ganancia ${gananciaPct.toFixed(1)}%, costos ${costoPct.toFixed(1)}% del ingreso` : "Sin ingreso"}>
      <circle cx="21" cy="21" r={RADIO} fill="none" stroke="var(--line-soft)" strokeWidth="6" />
      {revenue > 0 && (
        <>
          <circle cx="21" cy="21" r={RADIO} fill="none" stroke={PROFIT_COLOR} strokeWidth="6"
            strokeDasharray={`${gananciaPct} ${100 - gananciaPct}`} strokeDashoffset="25" />
          <circle cx="21" cy="21" r={RADIO} fill="none" stroke={COST_COLOR} strokeWidth="6"
            strokeDasharray={`${costoPct} ${100 - costoPct}`} strokeDashoffset={25 - gananciaPct} />
        </>
      )}
    </svg>
  );
}

export const DONUT_COLORS = { profit: PROFIT_COLOR, cost: COST_COLOR };

/** Barra apilada del costo por concepto. */
export function CostBar({ parts }: { parts: { key: string; label: string; value: number }[] }) {
  const total = parts.reduce((s, p) => s + Math.max(0, p.value), 0);
  if (total <= 0) return <div className="jobcost-bar is-empty" aria-label="Sin costos todavía" />;
  return (
    <div className="jobcost-bar" role="img"
      aria-label={parts.filter((p) => p.value > 0).map((p) => `${p.label} ${((p.value / total) * 100).toFixed(0)}%`).join(", ")}>
      {parts.filter((p) => p.value > 0).map((p) => (
        <span key={p.key} style={{ width: `${(p.value / total) * 100}%`, background: CONCEPT_COLORS[p.key] ?? "#999" }}
          title={p.label} />
      ))}
    </div>
  );
}
