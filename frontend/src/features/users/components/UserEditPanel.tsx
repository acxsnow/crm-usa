import { useState } from "react";
import { useUpdateUser, useUpdateUserRoles } from "../queries";
import type { OrgUser, Role } from "@/types/users";

/** Mensaje del backend, que explica la regla concreta que se incumplió. */
function mensajeDeError(err: unknown, porDefecto: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? porDefecto;
}

function mismosRoles(a: string[], b: string[]): boolean {
  return a.length === b.length && a.every((code) => b.includes(code));
}

/**
 * Edición de una persona: su nombre y sus roles.
 *
 * Los roles solo se podían elegir al invitar; si alguien cambiaba de área, no
 * había forma de ajustarlo sin tocar la base de datos.
 *
 * Quien lo monta debe pasarle `key={user.id}`: el estado inicial se toma de
 * `user` al montar, así que sin la clave, abrir la edición de otra fila con el
 * panel ya abierto conservaría el nombre y los roles de la persona anterior.
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
  // Lo último que quedó realmente guardado. Comparar contra `user` no sirve:
  // esa prop no se refresca tras guardar, así que un segundo guardado que
  // revirtiera el cambio no enviaría nada y aun así diría "guardado".
  const [persistido, setPersistido] = useState({
    nombre: user.full_name,
    roles: user.roles,
  });
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

    const nombreLimpio = nombre.trim();
    if (!nombreLimpio) {
      setError("El nombre es obligatorio.");
      return;
    }
    if (seleccionados.length === 0) {
      setError("La persona debe tener al menos un rol.");
      return;
    }

    const cambioNombre = nombreLimpio !== persistido.nombre;
    const cambiaronRoles = !mismosRoles(seleccionados, persistido.roles);
    if (!cambioNombre && !cambiaronRoles) {
      setAviso("No hay cambios que guardar.");
      return;
    }

    try {
      // Los roles van primero porque son los que el backend puede rechazar
      // (dejar la organización sin administrador). Si fallan, el nombre no se
      // llega a tocar y el panel queda igual que antes, sin cambios a medias.
      if (cambiaronRoles) {
        await guardarRoles.mutateAsync({ userId: user.id, roleCodes: seleccionados });
      }
      if (cambioNombre) {
        await guardarNombre.mutateAsync({ userId: user.id, fullName: nombreLimpio });
      }
      setPersistido({ nombre: nombreLimpio, roles: seleccionados });
      setAviso("Cambios guardados.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudieron guardar los cambios."));
    }
  }

  return (
    <div className="user-edit-panel">
      <div className="user-edit-header">
        <h2>Editar a {persistido.nombre}</h2>
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
        <button className="primary-button" onClick={guardar} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar"}
        </button>
      </div>
    </div>
  );
}
