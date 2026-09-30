import type { ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { billingKeys, getBillingDashboard, money, shortDay } from "./billingApi";
import { REJECTION_CATEGORIES, type BillingDashboard } from "@/types/billing";

const dias = (n: number) => (n === 0 ? "Hoy" : n === 1 ? "1 día" : `${n} días`);

type StageKey = "to_create" | "to_submit" | "submitted" | "rejected" | "paid";

/**
 * Bandeja de cobros (spec D6.10), con el lenguaje del acta: arriba el camino
 * que recorre cada cobro, con cuántos hay en cada etapa; tocar una etapa
 * muestra su lista. Debajo del camino, lo que deben los programas por
 * antigüedad (la vista de Contabilidad).
 */
export function ClaimsInbox() {
  const { data, isLoading, error } = useQuery({ queryKey: billingKeys.dashboard, queryFn: getBillingDashboard });
  const [params, setParams] = useSearchParams();
  if (isLoading) return <p className="billing-empty">Cargando…</p>;
  if (error || !data) return <p className="form-error">No se pudo cargar el tablero de cobros.</p>;

  const alertas = (l: { alert: boolean }[]) => l.filter((i) => i.alert).length;
  const pagadoMes = data.paid_this_month.reduce((a, p) => a + p.paid_amount, 0);
  const etapas: { key: StageKey; title: string; count: number; note: string; alert: boolean; done?: boolean }[] = [
    { key: "to_create", title: "Por cobrar", count: data.to_create.length, alert: alertas(data.to_create) > 0,
      note: data.to_create.length ? (alertas(data.to_create) ? `${alertas(data.to_create)} desde ayer o antes` : "confirmadas hoy") : "al día" },
    { key: "to_submit", title: "Por radicar", count: data.to_submit.length, alert: alertas(data.to_submit) > 0,
      note: data.to_submit.length ? `${data.to_submit.filter((i) => i.ready_to_submit).length} listos para radicar` : "al día" },
    { key: "submitted", title: "Radicados", count: data.submitted.length, alert: alertas(data.submitted) > 0,
      note: alertas(data.submitted) ? `${alertas(data.submitted)} pasaron el plazo` : "dentro del plazo" },
    { key: "rejected", title: "Rechazados", count: data.rejected.length, alert: data.rejected.length > 0,
      note: data.rejected.length ? "en corrección" : "ninguno" },
    { key: "paid", title: "Pagados", count: data.paid_this_month.length, alert: false, done: true,
      note: `${money(pagadoMes)} este mes` },
  ];
  const porDefecto = etapas.find((e) => e.alert && e.key !== "paid")?.key ?? "to_submit";
  const elegida = (etapas.find((e) => e.key === params.get("etapa"))?.key ?? porDefecto) as StageKey;
  const elegir = (key: StageKey) => {
    const next = new URLSearchParams(params);
    next.set("etapa", key);
    setParams(next, { replace: true });
  };

  return (
    <>
      <section className="acta billing-flow" aria-label="Camino del cobro">
        <ol className="flow-rail">
          {etapas.map((e) => (
            <li key={e.key}>
              <button type="button" aria-pressed={elegida === e.key} onClick={() => elegir(e.key)}
                className={`flow-stage${e.alert ? " is-alert" : ""}${e.done && e.count ? " is-done" : ""}${elegida === e.key ? " is-selected" : ""}`}>
                <span className="flow-dot">{e.count}</span>
                <span className="flow-title">{e.title}</span>
                <span className="flow-note">{e.note}</span>
              </button>
            </li>
          ))}
        </ol>
        <Aging data={data} />
      </section>

      <section className="acta billing-list" aria-live="polite">
        <StageList data={data} stage={elegida} />
      </section>

      <ByProgram data={data} />
    </>
  );
}

function Aging({ data }: { data: BillingDashboard }) {
  const a = data.aging;
  const pct = (v: number) => (a.open_total ? `${(v / a.open_total) * 100}%` : "0%");
  return (
    <div className="flow-aging">
      <div className="flow-aging-total">
        <span>Lo que deben los programas</span>
        <strong className="money">{money(a.open_total)}</strong>
      </div>
      <div className="flow-aging-bar">
        <div className="aging-stack" role="img"
          aria-label={`0 a 30 días ${money(a.d0_30)}, 31 a 45 días ${money(a.d31_45)}, más de 45 días ${money(a.d46_plus)}`}>
          <i className="is-fresh" style={{ width: pct(a.d0_30) }} />
          <i className="is-aging" style={{ width: pct(a.d31_45) }} />
          <i className="is-late" style={{ width: pct(a.d46_plus) }} />
        </div>
        <dl className="aging-legend">
          <div><dt><span className="sw is-fresh" />0–30 días</dt><dd className="money">{money(a.d0_30)}</dd></div>
          <div><dt><span className="sw is-aging" />31–45 días</dt><dd className="money">{money(a.d31_45)}</dd></div>
          <div><dt><span className="sw is-late" />Más de 45</dt><dd className="money">{money(a.d46_plus)}</dd></div>
        </dl>
      </div>
    </div>
  );
}

const STAGE_COPY: Record<StageKey, { title: string; lead: string; empty: string }> = {
  to_create: { title: "Por cobrar", lead: "Actas confirmadas por Administración que todavía no tienen cobro. Ábrela y crea el cobro de cada programa.", empty: "Ninguna acta confirmada espera cobro." },
  to_submit: { title: "Por radicar", lead: "Cobros creados. Se radican cuando el checklist está completo.", empty: "No hay cobros por radicar." },
  submitted: { title: "Radicados, esperando pago", lead: "Se marca en rojo cuando pasan los días que el programa suele tardar en pagar.", empty: "No hay cobros radicados." },
  rejected: { title: "Rechazados, en corrección", lead: "No vencen: se corrigen y se vuelven a radicar.", empty: "Ningún cobro rechazado." },
  paid: { title: "Pagados este mes", lead: "Lo que llegó de los programas. Si pagaron distinto de la tarifa, se ve la diferencia.", empty: "Todavía no llega ningún pago este mes." },
};

function StageList({ data, stage }: { data: BillingDashboard; stage: StageKey }) {
  const copy = STAGE_COPY[stage];
  const filas: ReactNode[] = (() => {
    switch (stage) {
      case "to_create":
        return data.to_create.map((i) => (
          <Row key={i.project_id} to={`/projects/${i.project_id}`} main={i.customer_name} sub={[i.case_number, i.address]}
            status={<span className="billing-chip">Instalada {shortDay(i.installation_date)}</span>} days={i.days} alert={i.alert} />
        ));
      case "to_submit":
        return data.to_submit.map((i) => (
          <Row key={i.claim_id} to={`/invoices/claims/${i.claim_id}`} main={i.customer_name} sub={[i.case_number, i.address]}
            program={i.program_name} amount={i.amount} days={i.days} alert={i.alert}
            status={i.ready_to_submit ? <span className="billing-chip is-paid">Listo para radicar</span>
              : <span className="billing-chip is-preparing">Faltan {i.pending_requirements}</span>} />
        ));
      case "submitted":
        return data.submitted.map((i) => (
          <Row key={i.claim_id} to={`/invoices/claims/${i.claim_id}`} main={i.customer_name}
            sub={[i.case_number, `radicado el ${shortDay(i.submitted_on)}`]} program={i.program_name} amount={i.amount}
            status={<span className="billing-chip is-submitted">{i.days} de {i.expected_payment_days} días</span>}
            days={i.days} alert={i.alert} />
        ));
      case "rejected":
        return data.rejected.map((i) => (
          <Row key={i.claim_id} to={`/invoices/claims/${i.claim_id}`} main={i.customer_name}
            sub={[`${REJECTION_CATEGORIES[i.rejection_category ?? ""] ?? "Rechazo"}: ${i.rejection_reason ?? ""}`]}
            program={i.program_name} amount={i.amount} status={<span className="billing-chip is-rejected">Rechazado</span>}
            days={i.days} alert />
        ));
      case "paid":
        return data.paid_this_month.map((i) => (
          <Row key={i.claim_id} to={`/invoices/claims/${i.claim_id}`} main={i.customer_name}
            sub={[i.case_number, `pagado el ${shortDay(i.paid_on)}`]} program={i.program_name} amount={i.paid_amount}
            status={i.difference && Math.abs(i.difference) >= 0.01
              ? <span className="billing-chip is-rejected">{money(i.difference)}</span>
              : <span className="billing-chip is-paid">Completo</span>}
            days={i.days} alert={false} />
        ));
    }
  })();
  return (
    <>
      <header className="billing-list-head">
        <h2>{copy.title}</h2>
        <p>{copy.lead}</p>
      </header>
      {filas.length === 0 ? <p className="acta-empty">{copy.empty}</p> : <ul className="billing-rows">{filas}</ul>}
    </>
  );
}

function Row({ to, main, sub, program, amount, status, days, alert }: {
  to: string; main: string | null; sub: (string | null)[]; program?: string; amount?: number;
  status?: ReactNode; days: number; alert: boolean;
}) {
  return (
    <li>
      <Link to={to} className="billing-row">
        <span className="billing-row-main"><strong>{main ?? "Cliente"}</strong><span>{sub.filter(Boolean).join(" · ")}</span></span>
        {program ? <span className="billing-row-program">{program}</span> : <span />}
        {amount != null ? <span className="billing-amount">{money(amount)}</span> : <span />}
        {status ?? <span />}
        <span className={`billing-days${alert ? " is-alert" : ""}`}>{dias(days)}</span>
      </Link>
    </li>
  );
}

function ByProgram({ data }: { data: BillingDashboard }) {
  const p = data.particular;
  if (data.by_program.length === 0 && !p.outstanding_total && !p.draft_count) return null;
  return (
    <section className="acta billing-list" aria-label="Por programa">
      <header className="billing-list-head">
        <h2>Por programa</h2>
        <p>Lo que se espera cobrar a cada programa y lo que ya pagó este mes.</p>
      </header>
      {data.by_program.length > 0 && (
        <div className="billing-table-wrap">
          <table className="billing-table">
            <thead><tr><th>Programa</th><th className="num">Radicados</th><th className="num">Esperado</th><th className="num">Pagado este mes</th></tr></thead>
            <tbody>
              {data.by_program.map((r) => (
                <tr key={r.program_id}>
                  <td>{r.program_name}</td><td className="num">{r.submitted_count}</td>
                  <td className="num">{money(r.expected)}</td><td className="num">{money(r.paid_this_month)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="billing-row-note" style={{ marginTop: "0.9rem" }}>
        Trabajo particular: {p.overdue_count} {p.overdue_count === 1 ? "factura vencida" : "facturas vencidas"} ({money(p.overdue_total)}),
        {" "}{p.due_soon_count} por vencer en 7 días, saldo {money(p.outstanding_total)}
        {p.draft_count ? `, ${p.draft_count} en borrador` : ""}.
      </p>
    </section>
  );
}
