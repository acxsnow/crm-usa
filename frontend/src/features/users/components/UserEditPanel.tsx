import { useState } from "react";
import { useUpdateUser, useUpdateUserRoles } from "../queries";
import type { OrgUser, Role } from "@/types/users";

/** Mensaje del backend, que explica la regla concreta que se incumplió. */
function mensajeDeError(err: unknown, porDefecto: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? porDefecto;
}

/**
 * Edición de una persona: su nombre y sus roles.
 *
 * Los roles solo se podían elegir al invitar; si alguien cambiaba de área, no
 * había forma de ajustarlo sin tocar la base de datos.
 */
export function UserEditPanel({
  user,
  roles,
  onClose,
}: {
  user: OrgUser;
  roles: Role[];
  onClose: () => void;
}) {
  const [nombre, setNombre] = useState(user.full_name);
  const [seleccionados, setSeleccionados] = useState<string[]>(user.roles);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const guardarNombre = useUpdateUser();
  const guardarRoles = useUpdateUserRoles();
  const guardando = guardarNombre.isPending || guardarRoles.isPending;

  function alternarRol(code: string) {
    setSeleccionados((actuales) =>
      actuales.includes(code) ? actuales.filter((c) => c !== code) : [...actuales, code]
    );
  }

  async function guardar() {
    setError(null);
    setAviso(null);

    if (!nombre.trim()) {
      setError("El nombre es obligatorio.");
      return;
    }
    if (seleccionados.length === 0) {
      setError("La persona debe tener al menos un rol.");
      return;
    }

    try {
      if (nombre.trim() !== user.full_name) {
        await guardarNombre.mutateAsync({ userId: user.id, fullName: nombre.trim() });
      }
      const cambiaronRoles =
        seleccionados.length !== user.roles.length ||
        seleccionados.some((c) => !user.roles.includes(c));
      if (cambiaronRoles) {
        await guardarRoles.mutateAsync({ userId: user.id, roleCodes: seleccionados });
      }
      setAviso("Cambios guardados.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudieron guardar los cambios."));
    }
  }

  return (
    <div className="user-edit-panel">
      <div className="user-edit-header">
        <h2>Editar a {user.full_name}</h2>
        <button className="ghost-button" onClick={onClose}>
          Cerrar
        </button>
      </div>

      <p className="user-edit-email">{user.email}</p>

      <label className="field">
        <span>Nombre completo</span>
        <input value={nombre} onChange={(e) => setNombre(e.target.value)} />
      </label>

      <fieldset className="field">
        <legend>Roles</legend>
        <div className="role-checkboxes">
          {roles.map((role) => (
            <label key={role.code}>
              <input
                type="checkbox"
                checked={seleccionados.includes(role.code)}
                onChange={() => alternarRol(role.code)}
              />
              <span>{role.name}</span>
            </label>
          ))}
        </div>
        <small>
          Los permisos de cada rol se configuran en Roles y permisos. El cambio aplica en la
          siguiente carga de la persona.
        </small>
      </fieldset>

      {error && <p className="form-error">{error}</p>}
      {aviso && <p className="form-success">{aviso}</p>}

      <div className="role-actions">
        <button className="button-primary" onClick={guardar} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </div>
  );
}
