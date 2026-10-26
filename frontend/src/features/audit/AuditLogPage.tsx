import { useQuery } from "@tanstack/react-query";
import { listAuditEventsPage } from "./api";
import { listUsers } from "@/features/users/api";
import { useAuth } from "@/features/auth/AuthContext";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { PaginationControls } from "@/components/PaginationControls";
import { useTableFilters } from "@/lib/useTableFilters";
import type { AuditEvent } from "@/types/audit";

const PAGE_SIZE = 50;

const texto = (v: unknown) => (v === null || v === undefined || v === "" ? "—" : typeof v === "object" ? JSON.stringify(v) : String(v));

/** Antes → después de cada campo (D-020). Sin datos, nada. */
function Cambios({ evento }: { evento: AuditEvent }) {
  const antes = evento.before_data ?? {};
  const despues = evento.after_data ?? {};
  const campos = Array.from(new Set([...Object.keys(antes), ...Object.keys(despues)]));
  if (campos.length === 0) return <span>—</span>;
  return (
    <details>
      <summary>Ver cambios ({campos.length})</summary>
      <ul className="audit-changes">
        {campos.map((c) => (
          <li key={c}>
            <strong>{c}:</strong>{" "}
            {c in antes ? <><span>{texto(antes[c])}</span> → </> : null}
            <span>{texto(despues[c])}</span>
          </li>
        ))}
      </ul>
      {evento.ip_address && <small>Desde {evento.ip_address}</small>}
    </details>
  );
}

export function AuditLogPage() {
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["audit-events", page, extraParams],
    queryFn: () => listAuditEventsPage(page, PAGE_SIZE, extraParams),
  });
  // Nombre y filtro por persona: con `users.read` (Administración, Contabilidad,
  // Gerencia) o `users.manage`. Sin ninguno se muestra el identificador.
  const { hasPermission } = useAuth();
  const canListUsers = hasPermission("users.read") || hasPermission("users.manage");
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, enabled: canListUsers,
                                     retry: false, throwOnError: false });

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
    { key: "changes", header: "Cambios", render: (e) => <Cambios evento={e} /> },
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
