import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createCustomer, listCustomersPage } from "./api";
import { PaginationControls } from "@/components/PaginationControls";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import type { Customer } from "@/types/crm";
import { useAuth } from "@/features/auth/AuthContext";

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

  const createMutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setName("");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate({ legal_name: name });
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
    { key: "legal_name", header: "Nombre", render: (c) => <Link to={`/customers/${c.id}`}>{c.legal_name}</Link> },
    { key: "main_phone", header: "Teléfono", render: (c) => c.main_phone ?? "—" },
    { key: "email", header: "Email", render: (c) => c.email ?? "—" },
    { key: "status", header: "Estado", render: (c) => <span className={`status-pill status-${c.status}`}>{c.status}</span> },
  ];

  return (
    <div className="list-page">
      <div className="page-heading"><div><p className="eyebrow">RELACIONES</p><h1>Clientes</h1><p className="page-subtitle">Administra tu cartera y mantén cada relación al día.</p></div>{canCreate && <button className="primary-button" onClick={() => document.getElementById("new-customer")?.focus()}>+ Nuevo cliente</button>}</div>
      {canCreate && (
      <form className="inline-form compact-form" onSubmit={handleSubmit}>
        <span className="form-search">⌕</span>
        <input id="new-customer" placeholder="Nombre del cliente" value={name} onChange={(e) => setName(e.target.value)} required />
        <button className="primary-button" type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Guardando..." : "Agregar cliente"}
        </button>
      </form>
      )}

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={customers ?? []} isLoading={isLoading} getRowKey={(c) => c.id} emptyMessage="Sin clientes para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
