import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { activateUser, deactivateUser, inviteUser, listRoles, listUsers } from "./api";

const emptyForm = { email: "", full_name: "", role_codes: [] as string[] };

export function UsersPage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const { data: roles } = useQuery({ queryKey: ["roles"], queryFn: listRoles });

  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);

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

      {isLoading ? (
        <p>Cargando...</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Nombre</th>
              <th>Email</th>
              <th>Roles</th>
              <th>Estado</th>
              <th>Último acceso</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data?.items.map((user) => (
              <tr key={user.id}>
                <td>{user.full_name}</td>
                <td>{user.email}</td>
                <td>{user.roles.join(", ")}</td>
                <td>
                  <span className={`status-pill ${user.status === "active" ? "status-active" : "status-inactive"}`}>
                    {user.status}
                  </span>
                </td>
                <td>{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "—"}</td>
                <td>
                  {user.status === "active" ? (
                    <button
                      className="link-button"
                      disabled={deactivateMutation.isPending}
                      onClick={() => deactivateMutation.mutate(user.id)}
                    >
                      Desactivar
                    </button>
                  ) : (
                    <button
                      className="link-button"
                      disabled={activateMutation.isPending}
                      onClick={() => activateMutation.mutate(user.id)}
                    >
                      Activar
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
