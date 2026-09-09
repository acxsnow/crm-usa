import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { convertLead, createLead, listLeadsPage } from "./api";
import { PaginationControls } from "@/components/PaginationControls";
import { Link } from "react-router-dom";
import type { Lead } from "@/types/crm";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { useTableFilters } from "@/lib/useTableFilters";

const PAGE_SIZE = 20;

const BENEFIT_TYPES = ["CARE", "MEDICAL", "CALFRESH", "TAXES", "HEEHRA"];

const emptyForm = {
  full_name: "",
  phone: "",
  email: "",
  benefit_type: "",
  address_street: "",
  address_unit: "",
  address_city: "",
  address_state: "",
  address_zip: "",
};

export function LeadsPage() {
  const queryClient = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["leads", page, extraParams],
    queryFn: () => listLeadsPage(page, PAGE_SIZE, extraParams),
  });
  const leads = data?.items;
  const [form, setForm] = useState(emptyForm);
  const [duplicateWarning, setDuplicateWarning] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: createLead,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["leads"] });
      setForm(emptyForm);
      if (result.possible_duplicates.length > 0) {
        const names = result.possible_duplicates.map((d) => `${d.full_name} (${d.matched_on.join(", ")})`).join("; ");
        setDuplicateWarning(`Posible duplicado: ${names}`);
      } else {
        setDuplicateWarning(null);
      }
    },
  });

  const convertMutation = useMutation({
    mutationFn: convertLead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["leads"] }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.full_name.trim()) return;
    createMutation.mutate(form);
  }

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre, teléfono o email" },
    {
      key: "status",
      label: "Estado",
      type: "select",
      options: [
        { value: "new", label: "Nueva" },
        { value: "contacted", label: "Contactado" },
        { value: "qualified", label: "Calificado" },
        { value: "disqualified", label: "Descalificado" },
        { value: "converted", label: "Convertido" },
      ],
    },
  ];

  const columns: Column<Lead>[] = [
    { key: "full_name", header: "Nombre" },
    {
      key: "address",
      header: "Dirección",
      render: (l) => [l.address_street, l.address_unit, l.address_city].filter(Boolean).join(", ") || "—",
    },
    { key: "phone", header: "Teléfono", render: (l) => l.phone ?? "—" },
    { key: "benefit_type", header: "Beneficio", render: (l) => l.benefit_type ?? "—" },
    { key: "status", header: "Estado", render: (l) => <span className={`status-pill status-${l.status}`}>{l.status}</span> },
    {
      key: "actions",
      header: "",
      render: (l) => (
        <>
          <Link className="link-button" to={`/applications/new?leadId=${l.id}`}>
            Abrir aplicación
          </Link>{" "}
          {l.status !== "converted" && (
            <button className="link-button" disabled={convertMutation.isPending} onClick={() => convertMutation.mutate(l.id)}>
              Convertir
            </button>
          )}
        </>
      ),
    },
  ];

  return (
    <div className="list-page">
      <div className="page-heading"><div><p className="eyebrow">CAPTACIÓN PUERTA A PUERTA</p><h1>Prospectos</h1><p className="page-subtitle">Convierte cada visita en una oportunidad para tu equipo.</p></div><span className="page-badge">● Operación activa</span></div>
      <p className="page-subtitle">Personas contactadas puerta a puerta para el programa de aires acondicionados.</p>

      <form className="inline-form lead-form" onSubmit={handleSubmit}>
        <input
          placeholder="Nombre completo"
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          required
        />
        <input placeholder="Teléfono" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <input placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <select value={form.benefit_type} onChange={(e) => setForm({ ...form, benefit_type: e.target.value })}>
          <option value="">Beneficio...</option>
          {BENEFIT_TYPES.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
        <input
          placeholder="Dirección"
          value={form.address_street}
          onChange={(e) => setForm({ ...form, address_street: e.target.value })}
        />
        <input
          placeholder="Unidad/Espacio"
          value={form.address_unit}
          onChange={(e) => setForm({ ...form, address_unit: e.target.value })}
        />
        <input
          placeholder="Ciudad"
          value={form.address_city}
          onChange={(e) => setForm({ ...form, address_city: e.target.value })}
        />
        <button className="primary-button" type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Guardando..." : "Agregar lead"}
        </button>
      </form>
      {duplicateWarning && <p className="warning-banner">{duplicateWarning}</p>}

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={leads ?? []} isLoading={isLoading} getRowKey={(l) => l.id} emptyMessage="Sin prospectos para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
