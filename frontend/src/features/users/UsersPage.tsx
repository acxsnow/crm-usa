import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { activateUser, deactivateUser, inviteUser, listRoles, listUsersPage } from "./api";
import { FilterBar, type FilterFieldDef } from "@/components/FilterBar";
import { DataTable, type Column } from "@/components/DataTable";
import { PaginationControls } from "@/components/PaginationControls";
import { useTableFilters } from "@/lib/useTableFilters";
import { UserEditPanel } from "./components/UserEditPanel";
import type { OrgUser } from "@/types/users";

const PAGE_SIZE = 20;

const emptyForm = { email: "", full_name: "", role_codes: [] as string[] };

export function UsersPage() {
  const queryClient = useQueryClient();
  const { filters, page, setFilters, clearFilters, setPage, extraParams } = useTableFilters();
  const { data, isLoading } = useQuery({
    queryKey: ["users", page, extraParams],
    queryFn: () => listUsersPage(page, PAGE_SIZE, extraParams),
  });
  const { data: roles } = useQuery({ queryKey: ["roles"], queryFn: listRoles });

  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState<OrgUser | null>(null);

  const inviteMutation = useMutation({
    mutationFn: inviteUser,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      setForm(emptyForm);
      setError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "No se pudo invitar al usuario.");
    },
  });

  const activateMutation = useMutation({
    mutationFn: activateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  const deactivateMutation = useMutation({
    mutationFn: deactivateUser,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["users"] }),
  });

  function toggleRole(code: string) {
    setForm((f) => ({
      ...f,
      role_codes: f.role_codes.includes(code) ? f.role_codes.filter((c) => c !== code) : [...f.role_codes, code],
    }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!form.email.trim() || !form.full_name.trim() || form.role_codes.length === 0) {
      setError("Email, nombre y al menos un rol son obligatorios.");
      return;
    }
    inviteMutation.mutate(form);
  }

  const atLimit = data ? data.active_user_count >= data.max_active_users : false;

  const filterFields: FilterFieldDef[] = [
    { key: "q", label: "Buscar", type: "text", placeholder: "Nombre o email" },
    {
      key: "status",
      label: "Estado",
      type: "select",
      options: [
        { value: "invited", label: "Invitado" },
        { value: "active", label: "Activo" },
        { value: "inactive", label: "Inactivo" },
        { value: "locked", label: "Bloqueado" },
      ],
    },
    ...(roles && roles.length > 0
      ? [
          {
            key: "role",
            label: "Rol",
            type: "select" as const,
            options: roles.map((r) => ({ value: r.code, label: r.name })),
          },
        ]
      : []),
  ];

  const columns: Column<OrgUser>[] = [
    { key: "full_name", header: "Nombre" },
    { key: "email", header: "Email" },
    {
      key: "roles",
      header: "Roles",
      // Se muestra la etiqueta ("Vendedor"), no el código ("salesperson").
      render: (u) =>
        u.roles.map((code) => roles?.find((r) => r.code === code)?.name ?? code).join(", "),
    },
    {
      key: "status",
      header: "Estado",
      render: (u) => (
        <span className={`status-pill ${u.status === "active" ? "status-active" : "status-inactive"}`}>{u.status}</span>
      ),
    },
    { key: "last_login_at", header: "Último acceso", render: (u) => (u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "—") },
    {
      key: "actions",
      header: "",
      render: (u) => (
        <span className="row-actions">
          <button className="link-button" onClick={() => setEditando(u)}>
            Editar
          </button>
          {u.status === "active" ? (
            <button className="link-button" disabled={deactivateMutation.isPending} onClick={() => deactivateMutation.mutate(u.id)}>
              Desactivar
            </button>
          ) : (
            <button className="link-button" disabled={activateMutation.isPending} onClick={() => activateMutation.mutate(u.id)}>
              Activar
            </button>
          )}
        </span>
      ),
    },
  ];

  return (
    <div>
      <h1>Usuarios</h1>
      <p className="page-subtitle">Administra el equipo y sus roles dentro de la organización.</p>

      {data && (
        <p className="page-subtitle">
          {data.active_user_count} / {data.max_active_users} usuarios activos
          {atLimit && <span className="warning-banner" style={{ marginLeft: "0.5rem" }}>Límite del plan alcanzado</span>}
        </p>
      )}

      <form className="inline-form" onSubmit={handleSubmit} style={{ flexWrap: "wrap", alignItems: "flex-start" }}>
        <input
          placeholder="Email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
          required
        />
        <input
          placeholder="Nombre completo"
          value={form.full_name}
          onChange={(e) => setForm({ ...form, full_name: e.target.value })}
          required
        />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
          {(roles ?? []).map((role) => (
            <label key={role.code} style={{ display: "flex", alignItems: "center", gap: "0.25rem", fontSize: "0.85rem" }}>
              <input type="checkbox" checked={form.role_codes.includes(role.code)} onChange={() => toggleRole(role.code)} />
              {role.name}
            </label>
          ))}
        </div>
        <button type="submit" disabled={inviteMutation.isPending || atLimit}>
          {inviteMutation.isPending ? "Invitando..." : "Invitar usuario"}
        </button>
      </form>
      {error && <p className="warning-banner">{error}</p>}

      {editando && (
        <UserEditPanel
          // La clave fuerza un montaje nuevo al cambiar de persona: el estado
          // del panel se toma de `user` al montar, así que sin esto abrir otra
          // fila conservaría el nombre y los roles de la anterior.
          key={editando.id}
          user={editando}
          roles={roles ?? []}
          onClose={() => setEditando(null)}
        />
      )}

      <FilterBar fields={filterFields} values={filters} onApply={setFilters} onClear={clearFilters} />
      <DataTable columns={columns} rows={data?.items ?? []} isLoading={isLoading} getRowKey={(u) => u.id} emptyMessage="Sin usuarios para mostrar." />
      {data && <PaginationControls page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
    </div>
  );
}
