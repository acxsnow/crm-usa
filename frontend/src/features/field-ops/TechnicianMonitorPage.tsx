import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listTechnicianMonitor, updateTechnicianAvailability, type TechnicianMonitorRow } from "./api";
import { DataTable, type Column } from "@/components/DataTable";

export function TechnicianMonitorPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["technician-monitor"],
    queryFn: listTechnicianMonitor,
    refetchInterval: 30_000,
  });

  const toggleMutation = useMutation({
    mutationFn: ({ userId, isAvailable }: { userId: string; isAvailable: boolean }) =>
      updateTechnicianAvailability(userId, isAvailable),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["technician-monitor"] }),
  });

  const columns: Column<TechnicianMonitorRow>[] = [
    { key: "full_name", header: "Técnico" },
    {
      key: "logueado",
      header: "Logueado",
      render: (r) => <span className={`status-pill ${r.logueado ? "status-active" : "status-inactive"}`}>{r.logueado ? "Sí" : "No"}</span>,
    },
    {
      key: "en_cola",
      header: "En cola",
      render: (r) => (
        <button
          className="link-button"
          disabled={toggleMutation.isPending}
          onClick={() => toggleMutation.mutate({ userId: r.user_id, isAvailable: !r.en_cola })}
        >
          {r.en_cola ? "Disponible" : "No disponible"}
        </button>
      ),
    },
    { key: "casos_asignados", header: "Casos asignados" },
    { key: "casos_gestionados_hoy", header: "Casos gestionados hoy" },
    {
      key: "tiempo_gestion_hoy_dias",
      header: "Tiempo de gestión (hoy)",
      render: (r) => (r.tiempo_gestion_hoy_dias === null ? "—" : `${r.tiempo_gestion_hoy_dias.toFixed(1)} días`),
    },
  ];

  return (
    <div>
      <h1>Monitor de técnicos</h1>
      <p className="page-subtitle">Estado en vivo del equipo de campo — se actualiza automáticamente cada 30 segundos.</p>
      <DataTable columns={columns} rows={data ?? []} isLoading={isLoading} getRowKey={(r) => r.user_id} emptyMessage="Sin técnicos activos para mostrar." />
    </div>
  );
}
