import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { deleteCustomer, getCustomerTimeline, updateCustomer } from "./api";
import { confirmAction } from "@/components/ui/ConfirmDialog";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { ConsentCheckbox, DataConsentNotice, useConsentNotice } from "@/components/DataConsentNotice";
import { useState, type ReactNode } from "react";
import { useAuth } from "@/features/auth/AuthContext";
import { Avatar } from "@/components/ui/Avatar";
import { EmptyState } from "@/components/ui/EmptyState";
import { Icon, type IconName } from "@/components/ui/Icon";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { StatusBadge } from "@/components/ui/StatusBadge";

type Pestana = "resumen" | "expedientes" | "contactos";

const TIPO: Record<string, string> = { individual: "Persona", business: "Empresa" };
const ACTIVIDAD: Record<string, string> = {
  call: "Llamada", email: "Correo", meeting: "Reunión", note: "Nota", task: "Tarea", follow_up: "Seguimiento",
};

export function CustomerDetailPage() {
  const queryClient = useQueryClient();
  const { customerId } = useParams<{ customerId: string }>();
  const { data, isLoading } = useQuery({
    queryKey: ["customer-timeline", customerId],
    queryFn: () => getCustomerTimeline(customerId!),
    enabled: Boolean(customerId),
  });

  // Los hooks van antes de cualquier `return`: si se llaman después del
  // "Cargando…", React ve menos hooks en el primer render que en el segundo
  // y la página revienta («Rendered more hooks than during the previous render»).
  const [editing, setEditing] = useState(false);
  const [pestana, setPestana] = useState<Pestana>("resumen");
  // Editar es de `customers.update` (Vendedor, Administración, Administrador);
  // técnico, Contabilidad y Gerencia veían el botón y recibían un 403 (17 oct).
  const { hasPermission } = useAuth();
  const canEdit = hasPermission("customers.update");
  // D-014: borrar es de `customers.delete` (Administrador).
  const canDelete = hasPermission("customers.delete");
  const navigate = useNavigate();
  const [errorBorrar, setErrorBorrar] = useState<string | null>(null);
  const borrar = useMutation({
    mutationFn: () => deleteCustomer(customerId!),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["customers"] }); navigate("/customers"); },
    onError: (err) => setErrorBorrar(apiErrorMessage(err)),
    meta: { successMessage: "Cliente borrado." },
  });
  const [form, setForm] = useState({ legal_name: "", main_phone: "", email: "", billing_address: "", notes: "" });
  // La autorización de tratamiento de datos se pide al cambiar los datos
  // personales (el servidor aplica el mismo criterio: `PERSONAL_FIELDS`).
  const [autoriza, setAutoriza] = useState(false);
  const aviso = useConsentNotice();
  const updateMutation = useMutation({
    mutationFn: () => updateCustomer(customerId!, { ...form, data_consent_accepted: autoriza }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customer-timeline", customerId] });
      setEditing(false);
      setAutoriza(false);
    },
  });

  if (isLoading || !data) return <div className="customer-detail-page"><SkeletonRows rows={6} label="Cargando cliente…" /></div>;

  const { customer, cases, activities } = data;
  const PERSONALES = ["legal_name", "main_phone", "email", "billing_address"] as const;
  const cambianPersonales = PERSONALES.some((k) => (form[k] ?? "") !== (customer[k] ?? ""));
  const alternarEdicion = () => {
    if (!editing) {
      setForm({ legal_name: customer.legal_name, main_phone: customer.main_phone ?? "", email: customer.email ?? "",
        billing_address: customer.billing_address ?? "", notes: customer.notes ?? "" });
      setAutoriza(false);
    }
    setEditing(!editing);
  };

  const pestanas: { id: Pestana; label: string; count?: number }[] = [
    { id: "resumen", label: "Resumen" },
    { id: "expedientes", label: "Expedientes", count: cases.length },
    { id: "contactos", label: "Contactos", count: customer.contacts.length },
  ];

  return (
    <div className="customer-detail-page">
      <header className="ui-profile">
        <Avatar name={customer.legal_name} size="lg" />
        <div className="ui-profile-text">
          <p className="eyebrow">Perfil del cliente</p>
          <h1>{customer.legal_name}</h1>
          <div className="ui-profile-meta">
            <StatusBadge tone={customer.status === "active" ? "ok" : "neutral"}>{customer.status === "active" ? "Activo" : "Inactivo"}</StatusBadge>
            <span>{TIPO[customer.customer_type] ?? customer.customer_type}</span>
          </div>
        </div>
        {canEdit && <button className="primary-button ui-profile-action" onClick={alternarEdicion}>{editing ? "Cancelar" : "Editar cliente"}</button>}
        {canDelete && (
          <button type="button" className="secondary-button ui-profile-action" disabled={borrar.isPending}
            onClick={async () => {
              setErrorBorrar(null);
              const ok = await confirmAction({
                title: `¿Borrar a «${customer.legal_name}»?`,
                message: "Solo se puede si no tiene expedientes, obras, facturas ni cotizaciones. No se puede deshacer; "
                  + "las autorizaciones de datos que firmó se conservan.",
                confirmLabel: "Borrar", cancelLabel: "Dejarlo",
              });
              if (ok) borrar.mutate();
            }}>Borrar cliente</button>
        )}
      </header>
      {errorBorrar && <p className="form-error" role="alert">{errorBorrar}</p>}
      {canEdit && editing && <form className="edit-card" onSubmit={(e) => { e.preventDefault(); if (cambianPersonales && !autoriza) return; updateMutation.mutate(); }}><div className="edit-grid"><label>Nombre completo<input value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })} required /></label><label>Teléfono<input value={form.main_phone} onChange={(e) => setForm({ ...form, main_phone: e.target.value })} /></label><label>Correo<input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label><label>Dirección de facturación<input value={form.billing_address} onChange={(e) => setForm({ ...form, billing_address: e.target.value })} /></label><label className="wide-field">Notas<textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label></div>{cambianPersonales && <div className="ui-consent-block">{aviso.data && <DataConsentNotice notice={aviso.data} />}{aviso.data && <ConsentCheckbox notice={aviso.data} checked={autoriza} onChange={setAutoriza} />}</div>}<button className="primary-button" disabled={updateMutation.isPending || (cambianPersonales && !autoriza)}>{updateMutation.isPending ? "Guardando..." : "Guardar cambios"}</button>{cambianPersonales && !autoriza && <p className="form-help">Marca la autorización del cliente para guardar cambios en sus datos personales.</p>}{updateMutation.isError && <p className="form-error">No se pudieron guardar los cambios.</p>}</form>}

      <div className="ui-tabs" role="tablist" aria-label="Secciones del cliente">
        {pestanas.map((p) => (
          <button key={p.id} type="button" role="tab" id={`tab-${p.id}`} aria-controls={`panel-${p.id}`}
            aria-selected={pestana === p.id} className={pestana === p.id ? "ui-tab is-active" : "ui-tab"} onClick={() => setPestana(p.id)}>
            {p.label}{p.count !== undefined && <span className="ui-tab-count">{p.count}</span>}
          </button>
        ))}
      </div>

      {pestana === "resumen" && (
        <div className="ui-profile-grid" role="tabpanel" id="panel-resumen" aria-labelledby="tab-resumen">
          <section className="panel ui-info-card" aria-label="Datos de contacto">
            <Dato icon="phone" label="Teléfono">{customer.main_phone}</Dato>
            <Dato icon="mail" label="Correo">{customer.email}</Dato>
            <Dato icon="pin" label="Dirección de facturación">{customer.billing_address}</Dato>
            {customer.notes && <Dato icon="note" label="Notas">{customer.notes}</Dato>}
          </section>
          <section className="panel">
            <h2 className="ui-card-title">Actividades</h2>
            {activities.length === 0 ? (
              <EmptyState title="Sin actividades" description="Este cliente todavía no tiene actividades registradas." />
            ) : (
              <ul className="ui-timeline">
                {activities.map((a) => (
                  <li key={a.id}>
                    <span className="ui-timeline-dot" aria-hidden="true" />
                    <div>
                      <strong>{a.subject}</strong>
                      <small>{ACTIVIDAD[a.type] ?? a.type} · {new Date(a.created_at).toLocaleDateString("es-CO")}</small>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {pestana === "expedientes" && (
        <section role="tabpanel" id="panel-expedientes" aria-labelledby="tab-expedientes">
          {cases.length === 0 ? (
            <div className="panel"><EmptyState title="Sin expedientes" description="Este cliente todavía no tiene expedientes." /></div>
          ) : (
            <div className="table-wrap">
              <table className="data-table is-cards">
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
                      <td data-label="Expediente" className="is-title">{c.case_number}</td>
                      <td data-label="Etapa"><StatusBadge tone="info">{c.stage_label}</StatusBadge></td>
                      <td data-label="Dirección">{[c.address_street, c.address_unit].filter(Boolean).join(", ")}</td>
                      <td data-label="Abierto">{new Date(c.created_at).toLocaleDateString("es-CO")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {pestana === "contactos" && (
        <section role="tabpanel" id="panel-contactos" aria-labelledby="tab-contactos">
          {customer.contacts.length === 0 ? (
            <div className="panel"><EmptyState title="Sin contactos" description="Este cliente no tiene contactos adicionales." /></div>
          ) : (
            <ul className="ui-contact-list">
              {customer.contacts.map((c) => (
                <li key={c.id} className="panel">
                  <Avatar name={c.full_name} />
                  <div>
                    <strong>{c.full_name}</strong>{c.is_primary && <StatusBadge tone="info">Principal</StatusBadge>}
                    <small>{[c.role_title, c.phone, c.email].filter(Boolean).join(" · ") || "Sin datos de contacto"}</small>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

/** Un dato de la ficha con su ícono; «—» si está vacío. */
function Dato({ icon, label, children }: { icon: IconName; label: string; children: ReactNode }) {
  return (
    <div className="ui-info-row">
      <span className="ui-info-icon"><Icon name={icon} /></span>
      <div>
        <small>{label}</small>
        <span>{children || "—"}</span>
      </div>
    </div>
  );
}
