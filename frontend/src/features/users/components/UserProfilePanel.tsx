import { useQuery } from "@tanstack/react-query";
import { getUserProfile } from "../api";
import type { OrgUser } from "@/types/users";

const ESTADOS: Record<string, string> = { active: "Activo", invited: "Invitado", inactive: "Inactivo", locked: "Bloqueado" };
const ESTADOS_USA: Record<string, string> = { AZ: "Arizona", CA: "California", NV: "Nevada" };

/** «8 oct 2026»: con el mes en letras no se confunde día y mes. */
function fecha(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-US", { day: "numeric", month: "short", year: "numeric" });
}

/**
 * Ficha de solo lectura de una persona del equipo: quién es, cuándo entró y,
 * si vende, en qué programas y zonas. Nada se edita aquí; para eso está
 * «Editar». Antes, para saber las zonas de un vendedor había que revisar los
 * programas uno por uno.
 */
export function UserProfilePanel({ user, onClose }: { user: OrgUser; onClose: () => void }) {
  const { data: ficha, isLoading } = useQuery({ queryKey: ["user-profile", user.id], queryFn: () => getUserProfile(user.id) });

  return (
    <div className="user-edit-panel">
      <div className="user-edit-header">
        <h2>{user.full_name}</h2>
        <button className="ghost-button" onClick={onClose}>
          Cerrar
        </button>
      </div>
      <p className="user-edit-email">{user.email}</p>

      {isLoading || !ficha ? (
        <p className="page-subtitle">Cargando…</p>
      ) : (
        <>
          <dl className="user-profile-data">
            <div><dt>Perfil</dt><dd>{ficha.role_names.join(", ") || "—"}</dd></div>
            <div><dt>Estado</dt><dd>{ESTADOS[ficha.status] ?? ficha.status}</dd></div>
            {ficha.has_invitation ? (
              <>
                <div><dt>Invitado el</dt><dd>{fecha(ficha.invited_at)}{ficha.invited_by ? ` por ${ficha.invited_by}` : ""}</dd></div>
                <div><dt>Ingresó al equipo</dt><dd>{ficha.joined_at ? fecha(ficha.joined_at) : "Todavía no acepta la invitación"}</dd></div>
              </>
            ) : (
              <div><dt>Ingresó al equipo</dt><dd>{fecha(ficha.invited_at)} · creado sin invitación</dd></div>
            )}
            <div><dt>Último ingreso</dt><dd>{fecha(ficha.last_login_at)}</dd></div>
          </dl>

          {ficha.zones !== null && ficha.roles.includes("salesperson") && (
            <section className="user-profile-zones">
              <h3>Programas y zonas</h3>
              {ficha.zones.length === 0 ? (
                <p className="page-subtitle">
                  No tiene zonas asignadas. Puede vender cualquier programa con formulario publicado.
                </p>
              ) : (
                <ul>
                  {ficha.zones.map((z) => (
                    <li key={`${z.program_code}-${z.zone_name}`}>
                      <strong>{z.program_name}</strong> · {z.zone_name}
                      {z.city || z.state ? ` (${[z.city, z.state ? ESTADOS_USA[z.state] ?? z.state : null].filter(Boolean).join(", ")})` : ""}
                      {!z.active && <span className="status-pill status-inactive">Zona inactiva</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
        </>
      )}
    </div>
  );
}
