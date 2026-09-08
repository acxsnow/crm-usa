import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { createCustomer, listCustomersPage } from "./api";
import { PaginationControls } from "@/components/PaginationControls";

const PAGE_SIZE = 20;

export function CustomersPage() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const { data, isLoading } = useQuery({
    queryKey: ["customers", page],
    queryFn: () => listCustomersPage(page, PAGE_SIZE),
  });
  const customers = data?.items;
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: createCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customers"] });
      setName("");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    createMutation.mutate({ legal_name: name });
  }

  return (
    <div className="list-page">
      <div className="page-heading"><div><p className="eyebrow">RELACIONES</p><h1>Clientes</h1><p className="page-subtitle">Administra tu cartera y mantén cada relación al día.</p></div><button className="primary-button" onClick={() => document.getElementById("new-customer")?.focus()}>+ Nuevo cliente</button></div>
      <form className="inline-form compact-form" onSubmit={handleSubmit}>
        <span className="form-search">⌕</span>
        <input id="new-customer" placeholder="Nombre del cliente" value={name} onChange={(e) => setName(e.target.value)} required />
        <button className="primary-button" type="submit" disabled={createMutation.isPending}>
          {createMutation.isPending ? "Guardando..." : "Agregar cliente"}
        </button>
      </form>

      {isLoading ? (
        <p>Cargando...</p>
      ) : (
        <div className="table-wrap"><table className="data-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Teléfono</th>
              <th>Email</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {customers?.map((c) => (
              <tr key={c.id}>
                <td>
                  <Link to={`/customers/${c.id}`}>{c.legal_name}</Link>
                </td>
                <td>{c.main_phone}</td>
                <td>{c.email}</td>
                <td>
                  <span className={`status-pill status-${c.status}`}>{c.status}</span>
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
