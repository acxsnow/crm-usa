import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listApplicationsPage, updateApplication, type Application } from "./api";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";
import { PaginationControls } from "@/components/PaginationControls";

const PAGE_SIZE = 20;

const STATUS_OPTIONS = [
  { value: "pending_review", label: "Pendiente de revisión" },
  { value: "correction_requested", label: "Solicitar corrección" },
  { value: "ready_to_submit", label: "Lista para someter" },
  { value: "submitted", label: "Sometida" },
  { value: "approved", label: "Aprobada" },
  { value: "rejected", label: "Rechazada" },
];

export function ApplicationsAdminPage() {
  const client = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["applications", page, extraParams],
    queryFn: () => listApplicationsPage(page, PAGE_SIZE, extraParams),
  });
  const mutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updateApplication(id, { status }),
    onSuccess: () => client.invalidateQueries({ queryKey: ["applications"] }),
  });

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Código de programa" },
    { key: "status", label: "Estado", type: "select", options: STATUS_OPTIONS },
  ];

  const columns: Column<Application>[] = [
    {
      key: "program_code",
      header: "Programa",
      render: (app) => (
        <>
          <strong>{app.program_code}</strong>
          <br />
          <small>{app.id.slice(0, 8)}</small>
        </>
      ),
    },
    { key: "status", header: "Estado", render: (app) => <span className="status-pill">{app.status.split("_").join(" ")}</span> },
    { key: "created_at", header: "Creada", render: (app) => new Date(app.created_at).toLocaleDateString("es-CO") },
    {
      key: "review",
      header: "Revisión",
      render: (app) => (
        <select value={app.status} onChange={(e) => mutation.mutate({ id: app.id, status: e.target.value })}>
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      ),
    },
  ];

  return (
    <div className="list-page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">CONTROL ADMINISTRATIVO</p>
          <h1>Aplicaciones</h1>
          <p className="page-subtitle">Revisa la documentación antes de someter cada caso al programa.</p>
        </div>
      </div>
      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={data?.items ?? []} isLoading={isLoading} getRowKey={(app) => app.id} emptyMessage="Sin aplicaciones para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
