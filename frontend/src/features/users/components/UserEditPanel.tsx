import { useState } from "react";
import { useUpdateUser, useUpdateUserRoles } from "../queries";
import { useAuth } from "@/features/auth/AuthContext";
import type { OrgUser, Role } from "@/types/users";

/**
 * Roles que esta persona puede asignar. "Administrador" solo lo reparte otro
 * administrador: si no, cualquier rol propio con `users.manage` podría
 * ascender a alguien —o ascenderse— y quedarse con todos los permisos.
 *
 * Se deja visible el rol que la persona editada YA tiene, aunque no se pueda
 * otorgar: esconderlo haría que el botón de opción apareciera sin ninguno
 * marcado, como si no tuviera rol.
 */
export function rolesAsignables(roles: Role[], puedeDarAdmin: boolean, actuales: string[]): Role[] {
  if (puedeDarAdmin) return roles;
  return roles.filter((r) => r.code !== "organization_admin" || actuales.includes(r.code));
}

/** Mensaje del backend, que explica la regla concreta que se incumplió. */
function mensajeDeError(err: unknown, porDefecto: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? porDefecto;
}


/**
 * Edición de una persona: su nombre y su rol.
 *
 * El rol solo se podía elegir al invitar; si alguien cambiaba de área, no
 * había forma de ajustarlo sin tocar la base de datos.
 *
 * **Una persona tiene un rol y solo uno**, así que son botones de opción y no
 * casillas. La regla la impone la API (`role_codes` acepta exactamente uno);
 * aquí solo se refleja, porque esconder la opción en la pantalla no impide
 * mandar dos por HTTP.
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
  // Vacío solo si a la persona le borraron el rol que tenía; `guardar` lo exige.
  const [seleccionado, setSeleccionado] = useState<string>(user.roles[0] ?? "");
  // Lo último que quedó realmente guardado. Comparar contra `user` no sirve:
  // esa prop no se refresca tras guardar, así que un segundo guardado que
  // revirtiera el cambio no enviaría nada y aun así diría "guardado".
  const [persistido, setPersistido] = useState({
    nombre: user.full_name,
    rol: user.roles[0] ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const { user: actual } = useAuth();
  const asignables = rolesAsignables(roles, actual?.can_grant_admin ?? false, user.roles);
  const guardarNombre = useUpdateUser();
  const guardarRoles = useUpdateUserRoles();
  const guardando = guardarNombre.isPending || guardarRoles.isPending;

  async function guardar() {
    setError(null);
    setAviso(null);

    const nombreLimpio = nombre.trim();
    if (!nombreLimpio) {
      setError("El nombre es obligatorio.");
      return;
    }
    if (!seleccionado) {
      setError("Hay que elegir un rol.");
      return;
    }

    const cambioNombre = nombreLimpio !== persistido.nombre;
    const cambioRol = seleccionado !== persistido.rol;
    if (!cambioNombre && !cambioRol) {
      setAviso("No hay cambios que guardar.");
      return;
    }

    try {
      // Los roles van primero porque son los que el backend puede rechazar
      // (dejar la organización sin administrador). Si fallan, el nombre no se
      // llega a tocar y el panel queda igual que antes, sin cambios a medias.
      if (cambioRol) {
        await guardarRoles.mutateAsync({ userId: user.id, roleCodes: [seleccionado] });
      }
      if (cambioNombre) {
        await guardarNombre.mutateAsync({ userId: user.id, fullName: nombreLimpio });
      }
      setPersistido({ nombre: nombreLimpio, rol: seleccionado });
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
        <legend>Rol</legend>
        <div className="role-checkboxes">
          {asignables.map((role) => (
            <label key={role.code}>
              <input
                type="radio"
                name="rol-del-usuario"
                value={role.code}
                checked={seleccionado === role.code}
                onChange={() => setSeleccionado(role.code)}
              />
              <span>{role.name}</span>
            </label>
          ))}
        </div>
        <small>
          Cada persona tiene un solo rol. Los permisos de cada uno se configuran en Roles y
          permisos; el cambio aplica en la siguiente carga de la persona.
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
