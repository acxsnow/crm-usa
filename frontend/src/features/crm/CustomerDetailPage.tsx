import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getCustomerTimeline, updateCustomer } from "./api";
import { useState } from "react";

export function CustomerDetailPage() {
  const queryClient = useQueryClient();
  const { customerId } = useParams<{ customerId: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["customer-timeline", customerId],
    queryFn: () => getCustomerTimeline(customerId!),
    enabled: Boolean(customerId),
  });

  if (isLoading || !data) return <p>Cargando...</p>;

  const { customer, cases, activities } = data;
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({ legal_name: customer.legal_name, main_phone: customer.main_phone ?? "", email: customer.email ?? "", billing_address: customer.billing_address ?? "", notes: customer.notes ?? "" });
  const updateMutation = useMutation({ mutationFn: () => updateCustomer(customer.id, form), onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["customer-timeline", customerId] }); setEditing(false); } });

  return (
    <div className="customer-detail-page">
      <div className="page-heading"><div><p className="eyebrow">PERFIL DEL CLIENTE</p><h1>{customer.legal_name}</h1><p className="page-subtitle">Información de contacto, aplicaciones y trazabilidad.</p></div><button className="primary-button" onClick={() => setEditing(!editing)}>{editing ? "Cancelar" : "Editar cliente"}</button></div>
      {editing && <form className="edit-card" onSubmit={(e) => { e.preventDefault(); updateMutation.mutate(); }}><div className="edit-grid"><label>Nombre completo<input value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} required /></label><label>Teléfono<input value={form.main_phone} onChange={(e) => setForm({ ...form, main_phone: e.target.value })} /></label><label>Correo<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label><label>Dirección de facturación<input value={form.billing_address} onChange={(e) => setForm({ ...form, billing_address: e.target.value })} /></label><label className="wide-field">Notas<textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label></div><button className="primary-button" disabled={updateMutation.isPending}>{updateMutation.isPending ? "Guardando..." : "Guardar cambios"}</button>{updateMutation.isError && <p className="form-error">No se pudieron guardar los cambios.</p>}</form>}
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
        <h2>Expedientes</h2>
        {cases.length === 0 ? (
          <p className="muted">Este cliente todavía no tiene expedientes.</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Expediente</th>
                <th>Etapa</th>
                <th>Dirección</th>
                <th>Abierto</th>
              </tr>
            </thead>
            <tbody>
              {cases.map((c) => (
                <tr key={c.id}>
                  <td>{c.case_number}</td>
                  <td>{c.stage_label}</td>
                  <td>{[c.address_street, c.address_unit].filter(Boolean).join(", ")}</td>
                  <td>{new Date(c.created_at).toLocaleDateString("es-CO")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
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

    </div>
  );
}
