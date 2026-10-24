import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { listProjectsPage } from "./api";
import { listUsers } from "@/features/users/api";
import { useAuth } from "@/features/auth/AuthContext";
import { PaginationControls } from "@/components/PaginationControls";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import { PROJECT_STATUS_LABELS, type Project } from "@/types/fieldOps";

const PAGE_SIZE = 20;

export function ProjectsPage() {
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["projects", page, extraParams],
    queryFn: () => listProjectsPage(page, PAGE_SIZE, extraParams),
  });
  const projects = data?.items;
  // Solo quien puede ver la lista de usuarios (`users.read` o `users.manage`)
  // la pide; el técnico, que ve solo sus proyectos, se queda sin este filtro en
  // vez de recibir un 403 en cada visita.
  const { hasPermission } = useAuth();
  const canListUsers = hasPermission("users.read") || hasPermission("users.manage");
  const { data: allUsers } = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: canListUsers,
                                        retry: false, throwOnError: false });

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
    { key: "title", header: "Proyecto", render: (p) => (
      <>{p.title}{p.my_access === "read_only" && <span className="billing-chip read-only-chip">Solo lectura</span>}</>
    ) },
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
      {/* Sin «Crear proyecto»: el proyecto nace solo cuando el expediente pasa a
          «Aprobado» (field_ops/case_hooks.py). Uno creado a mano quedaba sin
          expediente, programa ni etapas (revisión del 19 oct). */}
      <p className="page-subtitle">Cada expediente aprobado crea su proyecto de instalación: permiso, instalación, acta y cobro.</p>

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={projects ?? []} isLoading={isLoading} getRowKey={(p) => p.id} emptyMessage="Sin proyectos para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
