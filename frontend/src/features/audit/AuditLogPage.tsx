import { useQuery } from "@tanstack/react-query";
import { listAuditEventsPage } from "./api";
import { listUsers } from "@/features/users/api";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { PaginationControls } from "@/components/PaginationControls";
import { useTableFilters } from "@/lib/useTableFilters";
import type { AuditEvent } from "@/types/audit";

const PAGE_SIZE = 50;

export function AuditLogPage() {
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["audit-events", page, extraParams],
    queryFn: () => listAuditEventsPage(page, PAGE_SIZE, extraParams),
  });
  // Best-effort actor lookup/filter: only org admins reach this page, and they
  // also carry users.manage, but fall back gracefully to the raw id if not.
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, retry: false, throwOnError: false });

  const actorName = (actorUserId: string | null) => {
    if (!actorUserId) return "Sistema";
    const match = users?.items.find((u) => u.id === actorUserId);
    return match ? match.full_name : actorUserId;
  };

  const filterFields: FilterFieldDef[] = [
    { key: "action", label: "Acción", type: "text", placeholder: "Ej. login, invited" },
    ...(users && users.items.length > 0
      ? [
          {
            key: "actor_user_id",
            label: "Actor",
            type: "select" as const,
            options: users.items.map((u) => ({ value: u.id, label: u.full_name })),
          },
        ]
      : []),
  ];

  const columns: Column<AuditEvent>[] = [
    { key: "created_at", header: "Fecha", render: (e) => new Date(e.created_at).toLocaleString() },
    { key: "actor", header: "Actor", render: (e) => actorName(e.actor_user_id) },
    { key: "action", header: "Acción" },
    {
      key: "entity",
      header: "Entidad",
      render: (e) => `${e.entity_type ?? "—"}${e.entity_id ? ` (${e.entity_id.slice(0, 8)}…)` : ""}`,
    },
  ];

  return (
    <div>
      <h1>Registro de auditoría</h1>
      <p className="page-subtitle">Historial de acciones relevantes: inicios de sesión, cambios de contraseña, invitaciones, activaciones y cambios de configuración.</p>

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={data?.items ?? []} isLoading={isLoading} getRowKey={(e) => e.id} emptyMessage="Sin eventos para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
