import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getCustomerTimeline } from "./api";

export function CustomerDetailPage() {
  const { customerId } = useParams<{ customerId: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["customer-timeline", customerId],
    queryFn: () => getCustomerTimeline(customerId!),
    enabled: Boolean(customerId),
  });

  if (isLoading || !data) return <p>Cargando...</p>;

  const { customer, opportunities, activities, quotes } = data;

  return (
    <div>
      <h1>{customer.legal_name}</h1>
      <p className="page-subtitle">
        {customer.main_phone} · {customer.email}
      </p>

      <section>
        <h2>Contactos</h2>
        <ul className="plain-list">
          {customer.contacts.map((c) => (
            <li key={c.id}>
              {c.full_name} {c.is_primary && "(principal)"} — {c.phone} {c.email}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Oportunidades</h2>
        <table className="data-table">
          <thead>
            <tr>
              <th>Título</th>
              <th>Etapa</th>
              <th>Programa</th>
              <th>Dirección</th>
            </tr>
          </thead>
          <tbody>
            {opportunities.map((o) => (
              <tr key={o.id}>
                <td>{o.title}</td>
                <td>{o.stage.name}</td>
                <td>{o.funder_program}</td>
                <td>{[o.address_street, o.address_unit].filter(Boolean).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section>
        <h2>Actividades</h2>
        <ul className="plain-list">
          {activities.map((a) => (
            <li key={a.id}>
              [{a.type}] {a.subject}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <h2>Cotizaciones</h2>
        <ul className="plain-list">
          {quotes.map((q) => (
            <li key={q.id}>
              {q.quote_number} — {q.currency} {q.total_amount.toFixed(2)} ({q.status})
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
