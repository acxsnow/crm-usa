# Módulo 5 — Proyecto, checklist técnico, evidencias, permisos e inspección

Fecha: 27 de septiembre de 2026. Autor: Mateo Mazo (Cadena B).
Base: `docs/cronograma-cadena-b.md` (módulo 5), `docs/contratos/case.md`,
`docs/contratos/case-entrega.md`, `docs/requerimientos-formularios-programas-delta-hvac.md`
§7 y §8, y el código de `main` en `b7e8a09` (esqueleto `Case`, SEG-07 cerrado,
`register_effect`, creación del proyecto desde el expediente).

---

## 1. Qué es esto

El tramo de campo del expediente: desde que Administración lo aprueba hasta que
el inspector municipal lo da por bueno.

```
approved → permit_in_progress → ready_to_install (install_scheduled)
         → installed → inspection_pending (inspection_approved) → billing_in_progress
                              ↑                     │
                              └──── inspección fallida (provisional)
```

La idea que ordena todo el módulo: **la etapa del expediente es consecuencia de
hechos registrados, no una casilla que alguien marca**. Nadie "pasa a Listo para
instalar": Administración registra que el permiso salió aprobado y el expediente
avanza solo. Nadie "pasa a Instalado": el técnico cierra la instalación y el
sistema verifica que el checklist y los equipos estén completos. Así el tablero
nunca dice algo que los datos no respaldan, y los reportes de tiempos por etapa
(PDF §7) miden lo que pasó en la calle.

Dos caminos llegan al mismo resultado y los dos están protegidos:

1. **Comandos de campo** (`/projects/{id}/permits`, `/installation/close`,
   `/inspections`…): registran el hecho y, si completa la etapa, mueven el
   expediente dentro de la misma transacción.
2. **Cambio manual** (`POST /cases/{id}/transition`, de José): sigue existiendo
   para Administración. Las **guardas** de este módulo impiden que por ahí se
   salte un hecho: no se puede pasar a `installed` a mano si el checklist no
   está completo.

## 2. Qué ya existía y qué se conserva

Todo lo de la fase 3 sigue: proyecto, checklist con plantilla, tareas y
comentarios, evidencias con marca de agua GPS y fecha, atestación con doble
firma y PDF, monitor de técnicos. José ya dejó hecho el primer punto
obligatorio de la semana del 1 de octubre: **el proyecto se crea al aprobarse el
expediente** (`field_ops/case_hooks.py`, `auto_create_project_from_case`), sin
commit propio y de forma idempotente. Este módulo construye encima de eso.

## 3. Decisiones

### D5.1 — Los comandos de campo mueven el expediente, con la separación de funciones intacta

`cases.transition()` exige, además del permiso de la etapa, que quien actúa sea
el vendedor dueño o tenga `cases.read_all` (SEG-07). Esa regla de dueño está
pensada para el vendedor. En campo, el técnico no es dueño del expediente ni
tiene `cases.read_all`, así que nunca podría cerrar una instalación.

Solución, sin tocar el motor de José: los comandos de campo autorizan con su
propia regla (permiso de la acción **y** proyecto asignado, igual que ya hace la
consulta de proyectos) y luego llaman a `transition()` con
`stages.SYSTEM_ACTOR` y el `actor_id` real, así la auditoría y el historial
siguen diciendo quién fue. **Antes de hacerlo comprueban que el usuario tenga el
permiso que el mapa exige para entrar a esa etapa** (`stages.permission_for`).
Si no lo tiene, el hecho se guarda y el expediente no avanza: lo moverá quien sí
pueda. Un técnico no puede liberar una orden ni un inspector cobrar, aunque el
dato que registró sea el último que faltaba.

Todo esto vive en un solo punto: `field_ops/case_flow.py`, `advance_case()`.

### D5.2 — Guardas asíncronas (cierra COD-08)

Las reglas de este módulo consultan la base: checklist completo, permisos
vigentes, inspección aprobada. Con las guardas síncronas no se podía. Cambio
mínimo en `cases/service.py`: si la guarda devuelve algo esperable, se espera.
Las síncronas siguen funcionando igual. Es la única línea que este módulo toca
en el paquete de José y va avisada en el resumen de entrega.

### D5.3 — Checklist configurable por programa, con condiciones y "No aplica"

- `ChecklistTemplate.program_id` (contrato del esqueleto): cada programa puede
  tener su plantilla. Al crear el proyecto se elige la del programa del
  expediente; si no hay, la plantilla por defecto de la organización.
- Cada ítem gana: `section` (agrupación: "Requisitos generales",
  "Instalación y cierre"), `evidence_category` (qué foto exige), `condition_code`
  (solo es obligatorio si esa condición aplica a la instalación) y
  `allows_not_applicable`.
- El proyecto lleva `installation_conditions`: la lista de condiciones que
  aplican a esa casa (`gas_equipment_removed`, `electrical_upgrade`,
  `pedestal_required`, `title_decal_required`, §8.3). Las marca quien conoce la
  casa: Administración o el técnico en campo.
- Un ítem **cuenta como obligatorio** si `is_required` y (no tiene condición o
  su condición está marcada en el proyecto).
- "No aplica" exige motivo y solo se permite en ítems que lo admiten. Si falta el
  equipo, se marca `No aplica` con motivo, no se deja en blanco.
- La plantilla sigue siendo una **copia** al aplicarse: editar la plantilla no
  cambia un proyecto en curso (regla de la fase 3, se conserva).

### D5.4 — Las 15 categorías de evidencia del §7.1, como códigos

`evidence.category` pasa de enum de Postgres (`before/during/after/damage/other`)
a texto con catálogo en código (`field_ops/catalogs.py`), igual que José hizo con
`stage_code`. Agregar una categoría no requiere migración ni `ALTER TYPE`. Las
filas existentes pasan a `additional_photo` o `additional_video` según su tipo;
la base local y Render no tienen evidencias (verificado por José en la migración
`0013`).

Si la evidencia se sube para un ítem del checklist que exige una categoría, se
toma esa categoría; si se manda otra distinta, se rechaza. Una foto de la
etiqueta exterior no puede terminar clasificada como fachada.

### D5.5 — Permiso municipal: registro, no trámite

Tabla `permits`, varias por proyecto (eléctrico y mecánico pueden ser dos).
Estados: `submitted`, `approved`, `rejected`, `not_required`. **Vencido no es un
estado**: se calcula desde `expires_on`, como `Task.is_overdue`. Guardar
"vencido" obligaría a una tarea programada que lo actualice y, si no corre, el
dato miente.

- Registrar el primer permiso con el expediente en `approved` lo pasa a
  `permit_in_progress`.
- Cuando todos los permisos del proyecto están **despejados** (aprobados y
  vigentes, o `not_required` con motivo) y el expediente está en
  `permit_in_progress`, pasa a `ready_to_install`.
- `not_required` existe porque no toda instalación requiere permiso. Lo que no se
  permite es saltarse la etapa sin dejar constancia de por qué.

El autollenado de formularios municipales queda fuera (módulo sin dueño, si el
cliente lo confirma).

### D5.6 — Inspección con intentos

Tabla `inspections`, una fila por intento. Resultado `pending`, `passed` o
`failed`. Solo puede haber una pendiente por proyecto.

- Agendar la inspección con el expediente en `installed` lo pasa a
  `inspection_pending`.
- Resultado `passed`: sub-estado `inspection_approved`. El paso a
  `billing_in_progress` es del módulo 6 (`billing.submit`); este módulo registra
  la guarda que lo exige.
- Resultado `failed`: el expediente vuelve a `ready_to_install` (transición
  **provisional** del mapa de José, pendiente de respuesta del cliente) y el
  proyecto vuelve a `scheduled` para el re-trabajo. El intento fallido queda
  en el historial: así se puede medir cuántas inspecciones fallan, que hoy el
  artefacto lista como métrica imposible.

### D5.7 — Equipos instalados como dato

Tabla `installed_equipment`: tipo (catálogo), marca, modelo, serial, cantidad,
unidad o espacio, notas. El cobro al programa (módulo 6) necesita el serial como
dato, no solo la foto de la etiqueta. **Cerrar la instalación exige al menos un
equipo registrado**, y una vez cerrada los equipos quedan congelados: cambiarlos
después dejaría una factura que no coincide con lo instalado.

### D5.8 — Materiales por orden (PDF §5.1)

Tabla `project_materials`: descripción, referencia, cantidad, unidad. Lo
gestiona Administración (`projects.update`); el técnico lo ve en su orden. No es
inventario: es la lista de lo que la orden necesita.

### D5.9 — Agenda y asignación

`PATCH /projects/{id}/schedule` (`dispatch.manage`): técnico y fecha. Valida que
el técnico sea un usuario activo de la organización. Si el expediente está en
`ready_to_install`, marca el sub-estado `install_scheduled` y emite
`installation.scheduled` (la "orden liberada" del cronograma).
`GET /dispatch/agenda`: Administración ve la de todos (`dispatch.manage`); el
técnico solo la suya (`dispatch.read_own`), que es lo que habilita "Mi agenda"
en el menú. El monitor GTR se conserva igual.

### D5.10 — Eventos

Se emiten **después del commit**, desde el servicio de campo, para no anunciar
algo que después se deshace: `installation.scheduled`, `installation.closed`,
`inspection.recorded`, `permit.recorded`. `project.created` se emite desde un
suscriptor de `case.stage_changed` (a `approved`), que corre tras el commit de
la transición. El módulo 7 los conecta a notificaciones.

## 4. Qué se corrige de lo heredado

- **El técnico no podía marcar el checklist**: la ruta exigía
  `checklists.manage`, que es de Administración. Pasa a `checklists.complete` más
  proyecto asignado.
- **Mensajes en inglés** en las rutas que este módulo toca (hallazgo COD-02):
  pasan a español con las excepciones de dominio de `app/shared/errors.py`.
- **`storage.py` y `watermark.py`** se mueven a `app/shared/files/` (contrato del
  esqueleto, era del 30 de septiembre). Se actualizan los tres importadores
  (`field_ops`, `billing`, `crm`) y las pruebas. No quedan reexportaciones en
  `field_ops`: dos rutas de importación para lo mismo es justo lo que el
  contrato quería evitar.

## 5. Tablas y cambios de esquema — migración `0014_field_ops_module5`

- `checklist_templates`: `program_id` (FK `programs`, nula).
- `checklist_template_items` y `project_checklist_items`: `section`,
  `evidence_category`, `condition_code`, `allows_not_applicable`. En
  `project_checklist_items` además `not_applicable`, `not_applicable_reason`.
- `projects`: `installation_conditions` (JSON, lista de códigos).
- `evidence.category`: enum → `String(40)`, con conversión de valores.
- Nuevas: `permits`, `inspections`, `installed_equipment`, `project_materials`.
  Todas con `organization_id` (`OrgScopedMixin`) y `project_id` con borrado en
  cascada.
- `downgrade()` real. Si José integra antes otra `0014`, esta se renumera
  (regla de integración).

## 6. API nueva

| Método y ruta | Permiso | Qué hace |
|---|---|---|
| `PATCH /projects/{id}/conditions` | `checklists.complete` | Marca las condiciones de la instalación |
| `PATCH /checklist-items/{id}` | `checklists.complete` | Completa, desmarca o marca "No aplica" con motivo |
| `GET/POST /projects/{id}/permits` | lectura del proyecto / `permits.manage` | Lista y registra permisos |
| `PATCH /permits/{id}` | `permits.manage` | Cambia estado, fechas y número |
| `GET/POST /projects/{id}/inspections` | lectura / `inspections.manage` | Lista y agenda inspecciones |
| `POST /inspections/{id}/result` | `inspections.manage` | Registra aprobada o fallida |
| `GET/POST /projects/{id}/equipment`, `DELETE /equipment/{id}` | lectura / `equipment.manage` | Equipos instalados |
| `GET/POST /projects/{id}/materials`, `DELETE /materials/{id}` | lectura / `projects.update` | Materiales de la orden |
| `PATCH /projects/{id}/schedule` | `dispatch.manage` | Asigna técnico y fecha |
| `POST /projects/{id}/installation/close` | `checklists.complete` | Cierra la instalación |
| `GET /dispatch/agenda` | `dispatch.manage` o `dispatch.read_own` | Agenda por rango de fechas |
| `GET /field-ops/catalogs` | lectura de proyectos | Categorías de evidencia, condiciones y tipos de equipo |

"Lectura del proyecto" es la regla existente: `projects.read_all` ve todos,
`projects.read_assigned` solo los suyos, y un proyecto ajeno responde 404.

## 7. Guardas registradas en el motor

| Transición | Exige |
|---|---|
| `approved → permit_in_progress` | Proyecto con al menos un permiso registrado |
| `permit_in_progress → ready_to_install` | Todos los permisos despejados |
| `ready_to_install → installed` | Checklist completo y al menos un equipo |
| `installed → inspection_pending` | Una inspección pendiente agendada |
| `inspection_pending → billing_in_progress` | Última inspección aprobada |
| `inspection_pending → ready_to_install` | Última inspección fallida |

Un expediente sin proyecto (no debería existir desde `approved`) falla estas
guardas con un mensaje que dice qué falta.

## 8. Frontend

En el detalle del proyecto: condiciones de la instalación, checklist agrupado
por sección con "No aplica", permisos, equipos, materiales, inspecciones y el
botón "Cerrar instalación" con la lista de lo que falta. Pantalla "Mi agenda"
para el técnico y la vista de agenda para Administración. Todo en español.

## 9. Qué NO entra

- Autollenado de formularios municipales (módulo sin dueño).
- Inventario de materiales y costos (rentabilidad, fuera de fase).
- Distinguir "inspección fallida" como etapa propia: depende del cliente; el
  intento fallido ya queda guardado, así que el dato no se pierde.
- Notificaciones reales (módulo 7): aquí solo se emiten los eventos.
- Validación de tipo real de archivo por contenido (SEG-02): es transversal a
  todas las subidas y va en su propia tarea sobre `shared/files`.

## 10. Pruebas

TDD. Por cada regla: el caso que pasa, el que se bloquea y el mensaje.

- Cada guarda de §7 bloquea y deja pasar.
- Cada comando mueve el expediente solo cuando el hecho completa la etapa, y no
  lo mueve si el usuario no tiene el permiso de la etapa siguiente.
- El técnico cierra su instalación y no la de otro (404).
- "No aplica" sin motivo, o en un ítem que no lo admite, se rechaza.
- Un ítem condicional no bloquea si su condición no aplica.
- Permiso vencido no cuenta como despejado.
- Inspección fallida devuelve a `ready_to_install` y conserva el intento.
- Equipos congelados tras el cierre.
- Categoría de evidencia fuera de catálogo o distinta a la del ítem: 400.
- Aislamiento por organización en cada ruta nueva.
- La migración sube y baja.
