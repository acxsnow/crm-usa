import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createCustomer, listCustomersPage } from "./api";
import { ConsentCheckbox, DataConsentNotice, useConsentNotice } from "@/components/DataConsentNotice";
import { PaginationControls } from "@/components/PaginationControls";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import type { Customer } from "@/types/crm";
import { useAuth } from "@/features/auth/AuthContext";
import { Avatar } from "@/components/ui/Avatar";
import { Icon } from "@/components/ui/Icon";
import { StatusBadge } from "@/components/ui/StatusBadge";

const PAGE_SIZE = 20;

export function CustomersPage() {
  // Crear clientes es de quien vende o administra (`customers.create`); el
  // técnico ve la cartera pero veía el formulario y recibía un 403 (17 oct).
  const canCreate = useAuth().hasPermission("customers.create");
  const queryClient = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["customers", page, extraParams],
    queryFn: () => listCustomersPage(page, PAGE_SIZE, extraParams),
  });
  const customers = data?.items;
  const [name, setName] = useState("");
  // El alta rápida se abre con «+ Nuevo cliente» (antes estaba siempre a la vista).
  const [alta, setAlta] = useState(false);
  // Sin la autorización de tratamiento de datos no se guarda el cliente.
  const [autoriza, setAutoriza] = useState(false);
  const aviso = useConsentNotice();

  const createMutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setName("");
      setAutoriza(false);
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim() || !autoriza) return;
    createMutation.mutate({ legal_name: name, data_consent_accepted: autoriza });
  }

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, email o teléfono" },
    {
      key: "status",
      label: "Estado",
      type: "select",
      options: [
        { value: "active", label: "Activo" },
        { value: "inactive", label: "Inactivo" },
      ],
    },
  ];

  const columns: Column<Customer>[] = [
    {
      key: "legal_name", header: "Nombre", render: (c) => (
        <Link to={`/customers/${c.id}`} className="ui-person">
          <Avatar name={c.legal_name} />
          <span className="ui-person-text">
            <span className="ui-person-name">{c.legal_name}</span>
            {/* En el celular el teléfono y el correo van bajo el nombre, no en filas aparte. */}
            <small className="ui-only-mobile">{[c.main_phone, c.email].filter(Boolean).join(" · ") || "Sin datos de contacto"}</small>
          </span>
        </Link>
      ),
    },
    { key: "main_phone", header: "Teléfono", className: "is-hide-mobile", render: (c) => c.main_phone ?? "—" },
    { key: "email", header: "Email", className: "is-hide-mobile", render: (c) => c.email ?? "—" },
    {
      key: "status", header: "Estado", className: "is-corner",
      render: (c) => <StatusBadge tone={c.status === "active" ? "ok" : "neutral"}>{ESTADO[c.status] ?? c.status}</StatusBadge>,
    },
  ];

  const abrirAlta = () => {
    setAlta(true);
    // El campo aparece en este mismo render; se enfoca en el siguiente cuadro.
    requestAnimationFrame(() => document.getElementById("new-customer")?.focus());
  };

  return (
    <div className="list-page">
      <div className="page-heading">
        <div><p className="eyebrow">Relaciones</p><h1>Clientes</h1><p className="page-subtitle">Administra tu cartera y mantén cada relación al día.</p></div>
        {canCreate && <button className="primary-button" aria-expanded={alta} aria-controls="alta-cliente" onClick={alta ? () => setAlta(false) : abrirAlta}>{alta ? "Cerrar" : "+ Nuevo cliente"}</button>}
      </div>
      {canCreate && alta && (
      <form id="alta-cliente" className="ui-quick-create" onSubmit={handleSubmit}>
        <label htmlFor="new-customer">Nuevo cliente</label>
        <div className="ui-quick-create-row">
          <input id="new-customer" placeholder="Nombre del cliente" value={name} onChange={(e) => setName(e.target.value)} required />
          <button className="primary-button" type="submit" disabled={createMutation.isPending || !autoriza}>
            {createMutation.isPending ? "Guardando..." : "Agregar cliente"}
          </button>
        </div>
        {aviso.data && <DataConsentNotice notice={aviso.data} />}
        {aviso.data && <ConsentCheckbox notice={aviso.data} checked={autoriza} onChange={setAutoriza} />}
        {createMutation.isError && (
          <p className="form-error" role="alert">No se pudo crear el cliente. Revisa los datos y la autorización.</p>
        )}
      </form>
      )}

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={customers ?? []} isLoading={isLoading} getRowKey={(c) => c.id} emptyMessage="Sin clientes para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
      {canCreate && !alta && (
        <button type="button" className="ui-fab" aria-label="Nuevo cliente" onClick={() => { window.scrollTo({ top: 0 }); abrirAlta(); }}>
          <Icon name="plus" size={24} />
        </button>
      )}
    </div>
  );
}

const ESTADO: Record<string, string> = { active: "Activo", inactive: "Inactivo" };
