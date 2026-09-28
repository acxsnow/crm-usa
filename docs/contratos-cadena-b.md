# Contrato de la Cadena B — para José

Lo que la Cadena B (Mateo: `field_ops`, `billing`, `notifications`) expone y
lo que cambió fuera de su paquete. Se actualiza con cada entrega. Detalle de
diseño: `docs/superpowers/specs/2026-09-27-modulo-5-campo-design.md`.

Última actualización: 27 de septiembre de 2026 · módulo 5 (backend y pantallas).

---

## 1. Lo que toqué fuera de mi paquete

Tres cambios, todos acordados en el contrato del esqueleto o en la agenda del 26
de septiembre:

- **`cases/service.py`, `transition()`**: las guardas pueden ser `async`; si la
  guarda devuelve algo esperable, se espera. Las síncronas siguen igual. Cierra
  **COD-08**. Prueba: `tests/test_field_flow_guards.py`.
- **`storage.py` y `watermark.py`** pasaron de `field_ops` a
  `app/shared/files/` (contrato del esqueleto). Cambié los importadores,
  incluidas dos líneas en `crm/router.py`. No quedan reexportaciones en
  `field_ops`: se importa desde `app.shared.files.storage`.
- **`tests/test_rbac_full.py`**: la prueba afirmaba que el técnico no podía
  marcar el checklist (403). Era el error: la ruta pedía `checklists.manage`.
  Ahora pide `checklists.complete` y la prueba espera 404 para un ítem
  inexistente.

## 2. Cómo mueve campo el expediente

Un solo punto: `field_ops/case_flow.py`, `advance_case()`.

- Los comandos de campo autorizan con su regla (permiso de la acción y proyecto
  asignado) y llaman a `transition()` con `stages.SYSTEM_ACTOR` y el `actor_id`
  real. Motivo: la regla de dueño de `_require_stage_permission` es del vendedor,
  y el técnico nunca es dueño del expediente.
- Antes de llamar, `advance_case()` exige que el usuario tenga
  `stages.permission_for(to_stage)`. Si no lo tiene, el hecho se guarda y el
  expediente no avanza. La separación de funciones de SEG-07 se mantiene.
- Mapa, guardas, efectos, historial y auditoría corren igual que por tu ruta.

**Para conversar:** si prefieres que la regla de dueño de
`_require_stage_permission` reconozca al técnico asignado del proyecto, se
puede quitar `SYSTEM_ACTOR` de aquí. Es un cambio en tu paquete; por eso no lo
hice.

## 3. Guardas y efectos registrados (`field_ops/case_hooks.py`)

| Transición | Guarda | Efecto |
|---|---|---|
| `pending_approval`/`on_hold → approved` | — | Crea el proyecto (tuyo) |
| `approved → permit_in_progress` | Al menos un permiso registrado | — |
| `permit_in_progress → ready_to_install` | Todos los permisos despejados | — |
| `ready_to_install → installed` | Checklist completo y un equipo | Proyecto `completed` |
| `installed → inspection_pending` | Inspección pendiente agendada | — |
| `inspection_pending → billing_in_progress` | Última inspección aprobada | — |
| `inspection_pending → ready_to_install` | Última inspección fallida | Reabre el proyecto |

Por tu ruta manual (`POST /cases/{id}/transition`) pasan las mismas guardas: sin
el hecho registrado, 400 con el motivo en español.

## 4. Eventos que emito (después del commit)

| Evento | Datos |
|---|---|
| `project.created` | `case_id`, `case_number`, `organization_id` (desde un suscriptor de `case.stage_changed`) |
| `permit.recorded` | `permit_id`, `project_id`, `organization_id`, `status` |
| `installation.scheduled` | `project_id`, `organization_id`, `technician_user_id`, `scheduled_date` |
| `installation.closed` | `project_id`, `organization_id`, `closed_by_user_id` |
| `inspection.recorded` | `inspection_id`, `project_id`, `organization_id`, `result` |

## 5. API nueva

| Método y ruta | Permiso |
|---|---|
| `PATCH /projects/{id}/conditions` | `checklists.complete` |
| `PATCH /checklist-items/{id}` (`is_complete`, `not_applicable`, `reason`) | `checklists.complete` |
| `GET/POST /projects/{id}/permits`, `PATCH /permits/{id}` | lectura / `permits.manage` |
| `GET/POST /projects/{id}/inspections`, `POST /inspections/{id}/result` | lectura / `inspections.manage` |
| `GET/POST /projects/{id}/equipment`, `DELETE /equipment/{id}` | lectura / `equipment.manage` |
| `GET/POST /projects/{id}/materials`, `DELETE /materials/{id}` | lectura / `projects.update` |
| `PATCH /projects/{id}/schedule` | `dispatch.manage` |
| `GET /projects/{id}/installation/gaps`, `POST /projects/{id}/installation/close` | lectura / `checklists.complete` |
| `GET /dispatch/agenda?date_from&date_to&technician_id` | `dispatch.manage` o `dispatch.read_own` |
| `GET /field-ops/catalogs` | lectura de proyectos |

"Lectura" = `projects.read_all`, o `projects.read_assigned` solo para los
proyectos asignados; lo ajeno responde 404.

## 6. Esquema — migración `0014`

`permits`, `inspections`, `installed_equipment`, `project_materials`;
`checklist_templates.program_id` (FK a tu `programs`); campos de sección,
categoría, condición y "No aplica" en los ítems; `projects.installation_conditions`;
`evidence.category` de enum a texto (15 categorías del §7.1). Si integras antes
otra `0014`, la renumero yo.

**Validación:** SQL generado en modo offline (`alembic upgrade 0013:0014 --sql`)
y revisado. **Contra Postgres: por verificar** (no había base local levantada).

## 7. Pendientes conocidos

- `PATCH /projects/{id}` (heredado) todavía deja cambiar `status`,
  `scheduled_date` y técnico sin pasar por los comandos. Hay que cerrarlo en el
  módulo 6 o antes: hoy permitiría marcar un proyecto `completed` sin cierre.
- Si un permiso se rechaza o vence con el expediente ya en «Listo para
  instalar», el expediente no retrocede. Falta decidir con el cliente si debe
  bloquear la instalación.
- Qué pasa con la inspección fallida sigue provisional (tu mapa): vuelve a
  «Listo para instalar».
- Pantallas sin verificar en navegador (sin base local); `tsc` y `vite build`
  limpios.
