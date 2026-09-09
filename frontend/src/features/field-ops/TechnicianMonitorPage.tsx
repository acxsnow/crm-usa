import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listTechnicianMonitor, updateTechnicianAvailability, type TechnicianMonitorRow } from "./api";
import { DataTable, type Column } from "@/components/DataTable";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";

const filterFields: FilterFieldDef[] = [
  { key: "q", label: "Buscar", type: "text", placeholder: "Nombre del técnico" },
  {
    key: "logueado",
    label: "Logueado",
    type: "select",
    options: [
      { value: "true", label: "Sí" },
      { value: "false", label: "No" },
    ],
  },
  {
    key: "en_cola",
    label: "En cola",
    type: "select",
    options: [
      { value: "true", label: "Disponible" },
      { value: "false", label: "No disponible" },
    ],
  },
];

export function TechnicianMonitorPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["technician-monitor"],
    queryFn: listTechnicianMonitor,
    refetchInterval: 30_000,
  });

  const [filters, setFilters] = useState<Record<string, string>>({});

  const toggleMutation = useMutation({
    mutationFn: ({ userId, isAvailable }: { userId: string; isAvailable: boolean }) =>
      updateTechnicianAvailability(userId, isAvailable),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["technician-monitor"] }),
  });

  // Client-side filtering: the monitor already fetches every active field
  // technician in one call (no pagination), so there's no server round-trip
  // to save by pushing this down to the backend.
  const rows = (data ?? []).filter((r) => {
    if (filters.q && !r.full_name.toLowerCase().includes(filters.q.toLowerCase())) return false;
    if (filters.logueado && String(r.logueado) !== filters.logueado) return false;
    if (filters.en_cola && String(r.en_cola) !== filters.en_cola) return false;
    return true;
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
      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={() => setFilters({})} />
      <DataTable columns={columns} rows={rows} isLoading={isLoading} getRowKey={(r) => r.user_id} emptyMessage="Sin técnicos para mostrar." />
    </div>
  );
}
