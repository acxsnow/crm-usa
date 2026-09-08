import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createProject, listProjectsPage, seedDefaultChecklistTemplate } from "./api";
import { listCustomers } from "@/features/crm/api";
import { PaginationControls } from "@/components/PaginationControls";

const PAGE_SIZE = 20;

export function ProjectsPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({ queryKey: ["projects", page], queryFn: () => listProjectsPage(page, PAGE_SIZE) });
  const projects = data?.items;
  // Dropdown for the create-project form needs the full customer list, not
  // a page of it — listCustomers() (unpaginated call, capped at the API's
  // 100-row default) is the right fit here, separate from listCustomersPage.
  const { data: customers } = useQuery({ queryKey: ["customers-all"], queryFn: listCustomers });

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

  if (isLoading) return <p>Cargando...</p>;

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

      <table className="data-table">
        <thead>
          <tr>
            <th>Proyecto</th>
            <th>Dirección</th>
            <th>Estado</th>
            <th>Programado</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {(projects ?? []).map((p) => (
            <tr key={p.id}>
              <td>{p.title}</td>
              <td>{[p.address_street, p.address_unit].filter(Boolean).join(", ")}</td>
              <td>
                <span className={`status-pill status-${p.status}`}>{p.status}</span>
              </td>
              <td>{p.scheduled_date ?? "—"}</td>
              <td>
                <Link className="link-button" to={`/projects/${p.id}`}>
                  Ver
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
