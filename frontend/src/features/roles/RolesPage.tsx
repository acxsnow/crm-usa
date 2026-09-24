import { useEffect, useState } from "react";
import { PermissionPicker } from "./components/PermissionPicker";
import {
  useCreateRole,
  useDeleteRole,
  usePermissionCatalog,
  useRoles,
  useUpdateRole,
} from "./queries";
import type { Role } from "@/types/users";

/** Mensaje del backend, que ya viene en español y explica la regla concreta. */
function mensajeDeError(err: unknown, porDefecto: string): string {
  const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return detail ?? porDefecto;
}

const CODIGO_VALIDO = /^[a-z][a-z0-9_]{2,49}$/;

export function RolesPage() {
  const { data: roles, isLoading: cargandoRoles, isError: errorRoles } = useRoles();
  const { data: catalog, isLoading: cargandoCatalogo } = usePermissionCatalog();
  const crear = useCreateRole();
  const actualizar = useUpdateRole();
  const borrar = useDeleteRole();

  const [seleccionado, setSeleccionado] = useState<string | null>(null);
  const [nombre, setNombre] = useState("");
  const [permisos, setPermisos] = useState<string[]>([]);
  const [creando, setCreando] = useState(false);
  const [codigoNuevo, setCodigoNuevo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);

  const rolActual: Role | undefined = roles?.find((r) => r.code === seleccionado);

  // Al cambiar de rol se carga su estado en el formulario.
  useEffect(() => {
    if (rolActual) {
      setNombre(rolActual.name);
      setPermisos(rolActual.permissions);
      setCreando(false);
      setError(null);
    }
  }, [rolActual?.code]); // eslint-disable-line react-hooks/exhaustive-deps

  function empezarCreacion() {
    setCreando(true);
    setSeleccionado(null);
    setCodigoNuevo("");
    setNombre("");
    setPermisos([]);
    setError(null);
    setAviso(null);
  }

  async function guardar() {
    setError(null);
    setAviso(null);
    try {
      if (creando) {
        if (!CODIGO_VALIDO.test(codigoNuevo)) {
          setError(
            "El código debe empezar por una letra minúscula y usar solo minúsculas, números y guion bajo (mínimo 3 caracteres)."
          );
          return;
        }
        if (!nombre.trim()) {
          setError("El nombre es obligatorio.");
          return;
        }
        const creado = await crear.mutateAsync({
          code: codigoNuevo,
          name: nombre.trim(),
          permissions: permisos,
        });
        setCreando(false);
        setSeleccionado(creado.code);
        setAviso("Rol creado.");
      } else if (rolActual) {
        await actualizar.mutateAsync({
          code: rolActual.code,
          name: nombre.trim(),
          permissions: permisos,
        });
        setAviso("Cambios guardados.");
      }
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo guardar el rol."));
    }
  }

  async function eliminar(role: Role) {
    setError(null);
    setAviso(null);
    if (!window.confirm(`¿Eliminar el rol "${role.name}"? Esta acción no se puede deshacer.`)) {
      return;
    }
    try {
      await borrar.mutateAsync(role.code);
      if (seleccionado === role.code) setSeleccionado(null);
      setAviso("Rol eliminado.");
    } catch (err) {
      setError(mensajeDeError(err, "No se pudo eliminar el rol."));
    }
  }

  if (cargandoRoles || cargandoCatalogo) {
    return <p className="loading-state">Cargando roles…</p>;
  }
  if (errorRoles || !roles || !catalog) {
    return <p className="form-error">No se pudieron cargar los roles. Recarga la página.</p>;
  }

  const bloqueado = Boolean(rolActual?.is_locked);

  return (
    <div className="roles-page">
      <div className="page-heading">
        <div>
          <h1>Roles y permisos</h1>
          <p className="page-subtitle">
            Define qué puede hacer cada rol. Los permisos están agrupados por módulo: si un rol
            no tiene ninguno de un módulo, ese módulo no le aparece en el menú.
          </p>
        </div>
        <button className="button-primary" onClick={empezarCreacion}>
          Crear rol
        </button>
      </div>

      {aviso && <p className="form-success">{aviso}</p>}

      <div className="roles-layout">
        <aside className="roles-list">
          {roles.map((role) => (
            <button
              key={role.code}
              type="button"
              className={role.code === seleccionado ? "role-item selected" : "role-item"}
              onClick={() => setSeleccionado(role.code)}
            >
              <span className="role-item-name">{role.name}</span>
              <span className="role-item-meta">
                {role.is_system ? "Sistema" : "Propio"} · {role.permissions.length} permisos ·{" "}
                {role.user_count} {role.user_count === 1 ? "usuario" : "usuarios"}
              </span>
            </button>
          ))}
          {roles.length === 0 && <p className="empty-state">Todavía no hay roles.</p>}
        </aside>

        <section className="role-detail">
          {!creando && !rolActual && (
            <p className="empty-state">Elige un rol de la lista o crea uno nuevo.</p>
          )}

          {(creando || rolActual) && (
            <>
              <div className="role-detail-header">
                <h2>{creando ? "Nuevo rol" : rolActual?.name}</h2>
                {rolActual && !rolActual.is_system && (
                  <button className="ghost-button danger" onClick={() => eliminar(rolActual)}>
                    Eliminar
                  </button>
                )}
              </div>

              {bloqueado && (
                <p className="info-banner">
                  El rol de Administrador siempre conserva todos los permisos. Si se pudieran
                  quitar, alguien podría dejarse sin acceso a esta pantalla y quedar sin forma de
                  volver a entrar.
                </p>
              )}

              {creando && (
                <label className="field">
                  <span>Código</span>
                  <input
                    value={codigoNuevo}
                    onChange={(e) => setCodigoNuevo(e.target.value.toLowerCase())}
                    placeholder="coordinador_zona"
                  />
                  <small>Identificador interno. No se puede cambiar después.</small>
                </label>
              )}

              <label className="field">
                <span>Nombre</span>
                <input
                  value={nombre}
                  onChange={(e) => setNombre(e.target.value)}
                  disabled={bloqueado}
                  placeholder="Coordinador de zona"
                />
              </label>

              {error && <p className="form-error">{error}</p>}

              <PermissionPicker
                catalog={catalog}
                selected={bloqueado ? catalog.permissions.map((p) => p.code) : permisos}
                onChange={setPermisos}
                disabled={bloqueado}
              />

              {!bloqueado && (
                <div className="role-actions">
                  <button
                    className="button-primary"
                    onClick={guardar}
                    disabled={crear.isPending || actualizar.isPending}
                  >
                    {crear.isPending || actualizar.isPending ? "Guardando…" : "Guardar"}
                  </button>
                  <span className="role-actions-hint">
                    {permisos.length} permiso{permisos.length === 1 ? "" : "s"} seleccionado
                    {permisos.length === 1 ? "" : "s"}
                  </span>
                </div>
              )}
            </>
          )}
        </section>
      </div>
    </div>
  );
}
