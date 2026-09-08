import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditEvents } from "./api";
import { listUsers } from "@/features/users/api";

export function AuditLogPage() {
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["audit-events", page], queryFn: () => listAuditEvents(page) });
  // Best-effort actor-name lookup: only org admins reach this page, and they
  // also carry users.manage, but fall back gracefully to the raw id if not.
  const { data: users } = useQuery({ queryKey: ["users"], queryFn: listUsers, retry: false, throwOnError: false });

  const actorName = (actorUserId: string | null) => {
    if (!actorUserId) return "Sistema";
    const match = users?.items.find((u) => u.id === actorUserId);
    return match ? match.full_name : actorUserId;
  };

  return (
    <div>
      <h1>Registro de auditoría</h1>
      <p className="page-subtitle">Historial de acciones relevantes: inicios de sesión, cambios de contraseña, invitaciones, activaciones y cambios de configuración.</p>

      {isLoading ? (
        <p>Cargando...</p>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Actor</th>
                <th>Acción</th>
                <th>Entidad</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((event) => (
                <tr key={event.id}>
                  <td>{new Date(event.created_at).toLocaleString()}</td>
                  <td>{actorName(event.actor_user_id)}</td>
                  <td>{event.action}</td>
                  <td>
                    {event.entity_type ?? "—"}
                    {event.entity_id ? ` (${event.entity_id.slice(0, 8)}…)` : ""}
                  </td>
                </tr>
              ))}
              {data?.items.length === 0 && (
                <tr>
                  <td colSpan={4} className="page-subtitle">
                    Sin eventos para mostrar.
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          <div className="inline-form" style={{ marginTop: "1rem" }}>
            <button type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
              Anterior
            </button>
            <span className="page-subtitle">Página {page}</span>
            <button
              type="button"
              disabled={(data?.items.length ?? 0) < 50}
              onClick={() => setPage((p) => p + 1)}
            >
              Siguiente
            </button>
          </div>
        </>
      )}
    </div>
  );
}
