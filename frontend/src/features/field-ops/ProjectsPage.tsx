import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createProject, listProjectsPage, seedDefaultChecklistTemplate } from "./api";
import { listCustomers } from "@/features/crm/api";
import { listUsers } from "@/features/users/api";
import { useAuth } from "@/features/auth/AuthContext";
import { PaginationControls } from "@/components/PaginationControls";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import { PROJECT_STATUS_LABELS, type Project } from "@/types/fieldOps";

const PAGE_SIZE = 20;

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["projects", page, extraParams],
    queryFn: () => listProjectsPage(page, PAGE_SIZE, extraParams),
  });
  const projects = data?.items;
  // Dropdown for the create-project form needs the full customer list, not
  // a page of it — listCustomers() (unpaginated call, capped at the API's
  // 100-row default) is the right fit here, separate from listCustomersPage.
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });
  // Solo quien puede ver la lista de usuarios (`users.read` o `users.manage`)
  // la pide; el técnico, que ve solo sus proyectos, se queda sin este filtro en
  // vez de recibir un 403 en cada visita.
  const { hasPermission } = useAuth();
  const canListUsers = hasPermission("users.read") || hasPermission("users.manage");
  const { data: allUsers } = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: canListUsers,
                                        retry: false, throwOnError: false });

  const [customerId, setCustomerId] = useState("");
  const [title, setTitle] = useState("");
  const [addressStreet, setAddressStreet] = useState("");

  const createMutation = useMutation({
    mutationFn: async () => {
      const template = await seedDefaultChecklistTemplate();
      return createProject({
        customer_id: customerId,
        title,
        address_street: addressStreet || undefined,
        project_type: "hvac_install",
        apply_checklist_template_id: template.id,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      setTitle("");
      setAddressStreet("");
    },
  });

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Título o dirección" },
    {
      key: "status",
      label: "Estado",
      type: "select",
      options: [
        { value: "planning", label: "Planeación" },
        { value: "scheduled", label: "Programado" },
        { value: "in_progress", label: "En progreso" },
        { value: "completed", label: "Completado" },
        { value: "cancelled", label: "Cancelado" },
      ],
    },
    ...(allUsers && allUsers.items.length > 0
      ? [
          {
            key: "technician_id",
            label: "Técnico",
            type: "select" as const,
            options: allUsers.items.map((u) => ({ value: u.id, label: u.full_name })),
          },
        ]
      : []),
  ];

  const columns: Column<Project>[] = [
    { key: "title", header: "Proyecto" },
    { key: "address", header: "Dirección", render: (p) => [p.address_street, p.address_unit].filter(Boolean).join(", ") || "—" },
    { key: "status", header: "Estado", render: (p) => <span className={`status-pill status-${p.status}`}>{PROJECT_STATUS_LABELS[p.status]}</span> },
    { key: "scheduled_date", header: "Programado", render: (p) => p.scheduled_date ?? "—" },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <Link className="link-button" to={`/projects/${p.id}`} state={{ backTo: "/projects", backLabel: "Proyectos" }}>
          Ver
        </Link>
      ),
    },
  ];

  return (
    <div>
      <h1>Proyectos</h1>
      <p className="page-subtitle">Un proyecto por dirección/espacio — instalación, evidencia y atestación.</p>

      <form
        className="inline-form"
        onSubmit={(e) => {
          e.preventDefault();
          if (customerId && title) createMutation.mutate();
        }}
      >
        <select value={customerId} onChange={(e) => setCustomerId(e.target.value)} required>
          <option value="">Cliente...</option>
          {(customers ?? []).map((c) => (
            <option key={c.id} value={c.id}>
              {c.legal_name}
            </option>
          ))}
        </select>
        <input placeholder="Título del proyecto" value={title} onChange={(e) => setTitle(e.target.value)} required />
        <input placeholder="Dirección" value={addressStreet} onChange={(e) => setAddressStreet(e.target.value)} />
        <button type="submit" disabled={createMutation.isPending}>
          Crear proyecto
        </button>
      </form>

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={projects ?? []} isLoading={isLoading} getRowKey={(p) => p.id} emptyMessage="Sin proyectos para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
