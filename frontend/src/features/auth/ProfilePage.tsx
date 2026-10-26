import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { apiClient } from "@/lib/apiClient";
import { apiErrorMessage } from "@/features/field-ops/module5Api";
import { useAuth } from "./AuthContext";

/**
 * «Mi perfil»: cada persona corrige su propio nombre (D-014: `profile.manage`
 * existía y no hacía nada). El correo y el rol los cambia el Administrador en
 * Equipo; la clave, con «¿Olvidaste tu contraseña?».
 */
export function ProfilePage() {
  const { user, hasPermission, refreshCurrentUser } = useAuth();
  const [nombre, setNombre] = useState(user?.full_name ?? "");
  const [error, setError] = useState<string | null>(null);
  const puedeEditar = hasPermission("profile.manage");
  const guardar = useMutation({
    mutationFn: async () => { await apiClient.patch("/auth/me", { full_name: nombre.trim() }); },
    onSuccess: async () => { setError(null); await refreshCurrentUser(); },
    onError: (err) => setError(apiErrorMessage(err)),
    meta: { successMessage: "Nombre guardado." },
  });

  function enviar(event: FormEvent) {
    event.preventDefault();
    if (nombre.trim()) guardar.mutate();
  }

  return (
    <div className="billing-page notices-page">
      <header className="billing-head">
        <div>
          <h1>Mi perfil</h1>
          <p>Tu nombre es el que ven los demás en las obras, los expedientes y los avisos.</p>
        </div>
      </header>
      <article className="acta">
        <form className="fin-form" onSubmit={enviar}>
          <label>
            Nombre completo
            <input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={255} required
              disabled={!puedeEditar} />
          </label>
          <p className="notices-hint">
            Correo: {user?.email} · Rol: {user?.role_names?.join(", ") || "—"}. Esos los cambia el Administrador.
          </p>
          {error && <p className="form-error" role="alert">{error}</p>}
          {puedeEditar ? (
            <button type="submit" className="acta-btn is-primary"
              disabled={guardar.isPending || !nombre.trim() || nombre.trim() === user?.full_name}>
              {guardar.isPending ? "Guardando…" : "Guardar"}
            </button>
          ) : (
            <p className="notices-hint">Tu rol no permite cambiar el nombre: pídeselo al Administrador.</p>
          )}
        </form>
      </article>
    </div>
  );
}
