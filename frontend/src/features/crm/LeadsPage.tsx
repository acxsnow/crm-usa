import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { convertLead, createLead, listLeadsPage } from "./api";
import { PaginationControls } from "@/components/PaginationControls";
import type { Lead } from "@/types/crm";

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
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["leads", page], queryFn: () => listLeadsPage(page, PAGE_SIZE) });
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

      {isLoading ? (
        <p>Cargando...</p>
      ) : (
        <div className="table-wrap"><table className="data-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Dirección</th>
              <th>Teléfono</th>
              <th>Beneficio</th>
              <th>Estado</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {leads?.map((lead: Lead) => (
              <tr key={lead.id}>
                <td>{lead.full_name}</td>
                <td>
                  {[lead.address_street, lead.address_unit, lead.address_city].filter(Boolean).join(", ")}
                </td>
                <td>{lead.phone}</td>
                <td>{lead.benefit_type}</td>
                <td>
                  <span className={`status-pill status-${lead.status}`}>{lead.status}</span>
                </td>
                <td>
                  {lead.status !== "converted" && (
                    <button
                      className="link-button"
                      disabled={convertMutation.isPending}
                      onClick={() => convertMutation.mutate(lead.id)}
                    >
                      Convertir
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
