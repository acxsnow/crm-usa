# Contrato: `Case` (expediente)

Fecha: 21 de septiembre de 2026. Propuesto por José Javier sobre la
sugerencia de campos de Mateo. Estado: **borrador para acordar entre los
dos esta semana**; se implementa como esqueleto del 28 al 30 de septiembre.
Base: `decisiones.md` D2, D6 y D8.

Regla del documento: lo que aquí queda acordado no cambia sin avisar al
otro. Los campos marcados "por confirmar" se cierran antes del 28.

---

## 1. Campos definitivos de `Case`

Paquete `app/modules/cases/`. Tabla `cases`. Mixins del repo:
`UUIDPKMixin`, `TimestampMixin`, `OrgScopedMixin`.

Identidad:

- `id`: UUID.
- `organization_id`: UUID (mixin).
- `case_number`: str, único por organización, legible. Formato
  `CASE-AAAA-NNNN` (secuencia por organización y año). Se genera en el
  service al crear; nunca se edita.
- `source`: str. Valores: `visit` (puerta tocada), `lead` (convertido desde
  un Lead), `import` (CSV), `manual` (creado por Administración),
  `migration` (venía de Opportunity/Application).

Programa y flujo:

- `program_id`: UUID | null. Nulo mientras la puerta no responde; obligatorio
  desde `Nuevo Prospecto`.
- `program_version_id`: UUID | null. La versión del flujo con la que nació;
  se fija al pasar a `Nuevo Prospecto` y no cambia.
- `zone_id`: UUID | null. Zona del programa (D5).

Personas:

- `customer_id`: UUID | null. Nulo hasta que alguien abra y dé sus datos.
- `lead_id`: UUID | null. Si el case nació de un Lead existente.
- `assigned_salesperson_id`: UUID | null. Vendedor que abrió el case.
- `assigned_admin_id`: UUID | null. Persona de Administración que lo revisa
  (lo asigna el módulo 4).
- **Por confirmar:** `assigned_technician_id` **no** va en `Case`. El
  técnico se asigna al `Project` (módulo 5), que es donde se agenda y se
  ejecuta. Tenerlo en los dos crea dos verdades. Si Mateo lo quiere en
  `Case` para el Kanban, se expone como campo calculado desde `Project`.

Propiedad (la puerta):

- `address_street`: str | null.
- `address_unit`: str | null (número de unidad o espacio en el parque).
- `address_city`: str | null.
- `address_state`: str | null (CA, AZ, NV).
- `address_zip`: str | null.
- `latitude`: float | null.
- `longitude`: float | null.
- `normalized_address`: str | null. Calculada con `shared/normalize.py`
  al guardar. Índice por (`organization_id`, `normalized_address`,
  `address_unit`) para reutilizar el case de la misma puerta (D6). No es
  unique: una propiedad puede tener un case cerrado y otro abierto años
  después; la regla "un solo case abierto por propiedad" vive en el service.

Etapa:

- `stage_code`: str, obligatorio. Uno de los 15 de la sección 3.
- `substatus_code`: str | null. Definido por el dueño de la etapa.
- `stage_reason`: str | null. Motivo del último cambio (devolución,
  rechazo, no interesado…). Se copia del último `case_stage_event`.

Datos del programa (los llena Administración, módulo 4):

- `application_number`: str | null.
- `approval_code`: str | null.
- `funder_status_code`: str | null. **Por confirmar:** hoy existe la tabla
  `funder_statuses` por organización con FK; propongo dejar el **código**
  (`pending`, `in_review`, `approved`, `installed`, `rejected`, `waiting`)
  y mantener la tabla solo como catálogo de etiquetas. Menos joins y
  portable entre organizaciones.

Fechas hito (denormalizadas para consultas rápidas; **solo las escribe
`transition()`**, nunca un endpoint directo, para que no se desincronicen
del historial):

- `first_contact_at`: datetime | null. Primera vez que alguien abrió.
- `submitted_at`: datetime | null. Pasó a `Pendiente Aprobación`.
- `approved_at`: datetime | null. Pasó a `Aprobado`.
- `scheduled_install_date`: date | null. La fija el módulo 5.
- `completed_at`: datetime | null. Pasó a `Instalado`.
- `closed_at`: datetime | null. Pasó a `Cerrado` o a un cierre temprano.
- `created_at`, `updated_at`: mixin.

Lo que **no** va en `Case` y dónde vive:

- Respuestas del formulario → `step_submissions` (módulo 2).
- T&C aceptados y firma del cliente → `case_terms_acceptances` y archivo
  de firma (módulo 2).
- Documentos y fotos del vendedor → `case_documents` (módulo 3).
- Evidencias de instalación → `evidence` (módulo 5, Mateo).
- Permiso, inspección, equipos → tablas del módulo 5 con `case_id` o
  `project_id`.
- Invoices → `invoices.case_id` (módulo 6).

## 2. Tabla `case_stage_events`

Historial inmutable. Una fila por cada cambio de etapa o sub-estado.

- `id`: UUID.
- `organization_id`: UUID.
- `case_id`: UUID, FK a `cases`, índice.
- `from_stage_code`: str | null.
- `to_stage_code`: str.
- `from_substatus_code`: str | null.
- `to_substatus_code`: str | null.
- `reason`: str | null.
- `actor_user_id`: UUID | null (nulo si lo hizo el sistema).
- `occurred_at`: datetime.

Con esto se calcula: días en cada etapa, tiempo hasta aprobación, tasa de
rechazo, productividad por zona. Sin esto, ninguno de esos reportes del
PDF §7 es posible después.

## 3. Relaciones

- `Case.program_id` → `programs.id` (José, módulo 1). `Program` mínimo en
  el esqueleto: `id`, `organization_id`, `code`, `name`, `active`,
  `is_system_template`.
- `Case.program_version_id` → `program_versions.id` (José, módulo 1). En el
  esqueleto la tabla existe vacía.
- `Case.customer_id` → `customers.id` (existe). `Customer` no cambia.
- `Case.lead_id` → `leads.id` (existe). `Lead` no cambia.
- `Case.zone_id` → `program_zones.id` (José, módulo 1). En el esqueleto la
  tabla existe vacía.
- `Project.case_id` → `cases.id` (Mateo; la columna la agrega José en el
  esqueleto como única excepción). `Project.opportunity_id` se conserva
  hasta que se retire `Opportunity`.
- `ChecklistTemplate.program_id` → `programs.id` (Mateo, módulo 5).
- `InvoiceTemplate.program_id` → `programs.id` (Mateo, módulo 6).
- `Invoice.case_id` → `cases.id` (Mateo, módulo 6; hoy cuelga de `Project`,
  puede mantener ambos).
- Dirección de las flechas: **todo apunta a `Case` y a `Program`; `Case` y
  `Program` no apuntan a nada de la Cadena B.**

## 4. Etapas y transiciones

Etapas (`stage_code`), en orden:

- `no_contact` — Sin contacto (no abrió). Cierre temprano, reabrible.
- `not_interested` — No interesado. Cierre temprano, reabrible.
- `not_eligible` — No califica. Cierre temprano, reabrible.
- `new_prospect` — Nuevo Prospecto. Abrió, hay cliente, el vendedor está
  llenando el flujo.
- `pending_approval` — Pendiente Aprobación. El vendedor envió.
  Sub-estados (módulo 4): `pending_review`, `returned`, `ready_to_submit`,
  `submitted_to_program`, `program_review`.
- `approved` — Aprobado por el programa.
- `rejected` — Rechazado por el programa.
- `on_hold` — En espera (lista de espera del programa).
- `permit_in_progress` — Permiso en Trámite.
- `ready_to_install` — Listo para Instalar. Sub-estado (módulo 5):
  `install_scheduled`.
- `installed` — Instalado.
- `inspection_pending` — Inspección Pendiente. Sub-estado (módulo 5):
  `inspection_approved`; **por confirmar con el cliente** qué pasa si falla.
- `billing_in_progress` — En Proceso de Cobro. Sub-estados (módulo 6):
  `invoice_pending`, `submitted`, `rejected_by_program`.
- `paid` — Pagado.
- `closed` — Cerrado.

Transiciones permitidas (`from` → `to`) y quién es dueño de la regla:

Dueño José (módulo 2):

- (creación) → `no_contact` | `not_interested` | `not_eligible` | `new_prospect`.
- `no_contact` → `no_contact` (otra visita sin respuesta) | `not_interested`
  | `not_eligible` | `new_prospect`.
- `not_interested` → `new_prospect` (reabre).
- `not_eligible` → `new_prospect` (reabre, por ejemplo cambió de programa).
- `new_prospect` → `pending_approval` (solo si la validación de
  completitud pasa: campos, documentos, T&C, firma). Escribe `submitted_at`.
- `new_prospect` → `not_interested` | `not_eligible`.
- `pending_approval` (sub-estado `returned`) → `new_prospect` no existe:
  la devolución **no** cambia la etapa; el vendedor corrige dentro de
  `pending_approval` y el sub-estado vuelve a `pending_review`. Así el
  contador de días de aprobación no se reinicia.

Dueño Mateo (módulo 4):

- `pending_approval` → `approved` (escribe `approved_at`) | `rejected` |
  `on_hold`.
- `on_hold` → `approved` | `rejected`.
- `rejected` → `pending_approval` (reapertura con corrección, si el
  programa lo permite).

Dueño Mateo (módulo 5):

- `approved` → `permit_in_progress`. Al entrar a `approved` se crea el
  `Project` automáticamente (una sola vez).
- `permit_in_progress` → `ready_to_install`.
- `ready_to_install` → `installed` (solo si el checklist técnico está
  completo). Escribe `completed_at`.
- `installed` → `inspection_pending`.
- `inspection_pending` → `billing_in_progress` (inspección aprobada) |
  `ready_to_install` (falló y hay re-trabajo; **por confirmar**).

Dueño Mateo (módulo 6):

- `billing_in_progress` → `paid` (solo con el expediente de cobro
  completo y pago registrado).
- `paid` → `closed`. Escribe `closed_at`.

Dueño compartido:

- Cualquier etapa → `closed` con motivo, solo `organization_admin`
  (cierre administrativo). Escribe `closed_at`.

Mecánica:

- Una sola función: `transition(db, case, to_stage, actor, reason=None,
  substatus=None)` en `app/modules/cases/service.py`.
- La tabla `ALLOWED_TRANSITIONS: dict[str, set[str]]` vive en
  `app/modules/cases/stages.py` y contiene **todas** las de arriba desde el
  esqueleto.
- Las reglas de guarda (por ejemplo "checklist completo") se registran por
  etapa: `register_guard("ready_to_install", "installed", fn)`. Cada cadena
  registra las suyas desde su propio paquete; nadie edita el de otro.
- `transition()` valida la transición, ejecuta las guardas, cambia
  `stage_code`/`substatus_code`/`stage_reason`, escribe la fecha hito que
  corresponda, inserta el `case_stage_event`, registra auditoría y emite
  `events.emit("case.stage_changed", {...})`.
- Cambiar solo el sub-estado: `set_substatus(db, case, substatus, actor,
  reason)`, misma mecánica sin cambio de etapa.
- **Nadie escribe `stage_code` directamente.** Test de repo que lo verifica.

## 5. Dependencias entre módulos

- Módulo 0 (José, 21–25 sep): roles y permisos. `Case` no depende de él,
  pero `cases.*` y `programs.*` nacen como códigos de permiso reservados.
- Esqueleto (José, 28–30 sep): `programs`, `program_versions` (vacía),
  `program_zones` (vacía), `cases`, `case_stage_events`, `transition()`,
  `ALLOWED_TRANSITIONS`, `Project.case_id`, `shared/events.py`, migración
  de datos, Swagger. Mateo mueve `storage`/`watermark` a `shared/files/`.
- Módulo 5 (Mateo, desde 1 oct): usa `Case`, `transition()`, `Program.id`.
  Antes del 7 de octubre cambia el disparador del proyecto a `Case`.
- Módulo 1 (José, hasta 22 oct): llena `Program`, versiones, zonas,
  catálogo. Retira `Opportunity`/`Quote` la semana del 16.
- Módulo 6 (Mateo): `Invoice.case_id`, `InvoiceTemplate.program_id`.
- Módulo 2 (José): crea cases desde visitas, `step_submissions`, T&C,
  firma; transiciones hasta `pending_approval`.
- Módulo 3 (José): `case_documents`.
- Módulo 7 (Mateo): consume `case.stage_changed` y los demás eventos.
- Módulo 4 (Mateo, al final): transiciones `pending_approval` → salida.

## 6. Migración desde `Application` y `Opportunity`

Una sola migración de esquema en el esqueleto (`0009_cases`) y una de
datos a continuación (`0010_migrate_to_cases`). `downgrade()` real en ambas.

Esquema (`0009`):

- Crear `programs`, `program_versions`, `program_zones`, `cases`,
  `case_stage_events`.
- Agregar `projects.case_id` (nullable, FK, índice).
- No borrar nada.

Datos (`0010`):

- Por cada `Opportunity`: crear un `Program` por cada `funder_program`
  distinto que no exista (código en mayúsculas, `active=true`), y un
  `Case` con `source='migration'`, `customer_id`, dirección, `program_id`,
  `application_number`, `approval_code`, `funder_status_code`,
  `scheduled_install_date`, `assigned_salesperson_id = owner_user_id`, y
  `stage_code` según la etapa del pipeline:
  Nueva/Contactada → `new_prospect`; Solicitud enviada/En revisión →
  `pending_approval`; Aprobada → `approved`; Instalación →
  `ready_to_install`; Ganada → `installed`; Lista de espera → `on_hold`;
  Rechazada → `rejected`; Perdida → `not_interested`.
  Un `case_stage_event` inicial con `reason='migrated from opportunity'`.
- Por cada `Project` con `opportunity_id`: `case_id` = el case creado.
- Por cada `Application`: si tiene `customer_id` con una Opportunity
  migrada de la misma dirección, se asocia a ese `Case`; si no, se crea un
  `Case` nuevo (`source='migration'`, `stage_code` según `status`:
  draft → `new_prospect`, el resto → `pending_approval`, approved →
  `approved`, rejected → `rejected`). Sus `answers`, T&C y firma se copian
  a `step_submissions`/`case_terms_acceptances` **en el módulo 2**, cuando
  esas tablas existan; hasta entonces `applications` se conserva con una
  columna `case_id` para no perder nada.
- `Quote` y `QuoteLineItem`: no se migran (el PDF no cotiza); se archivan
  en un CSV de respaldo antes de borrar la tabla, en la semana del 16 de
  octubre.

Retiro (semana del 16 de octubre, módulo 1, ya con Mateo desenganchado):

- Borrar `projects.opportunity_id`, tablas `opportunities`, `quotes`,
  `quote_line_items`, `pipeline_stages`; endpoints y pantalla Pipeline;
  tests asociados. `applications` se borra al final del módulo 2, cuando
  sus datos ya viven en submissions.

Datos reales: hoy solo hay datos de demo (BD local y Render con seed).
Igual la migración se prueba con un dump de Render antes de aplicarla.

## 7. Impacto en la Cadena B

Lo que Mateo cambia, y cuándo:

- Antes del 7 de octubre: `field_ops/service.py` crea el `Project` desde
  `Case` (`approved`) en vez de `Opportunity` (`Aprobada`). Sus tests de
  auto-creación pasan a crear un `Case` y llamar `transition()`.
- Módulo 5: `Project` lee dirección y cliente desde `Case` (hoy los copia
  de `Opportunity`); `ChecklistTemplate.program_id`; transiciones de sus
  etapas registradas en `transition()`; eventos con `emit()`.
- Módulo 6: `Invoice.case_id`; `InvoiceTemplate.program_id`; transiciones
  de cobro.
- Módulo 4: transiciones de aprobación; `assigned_admin_id`.
- Frontend: `ProjectsPage`/`ProjectDetailPage` muestran `case_number` y
  enlazan al expediente; `OpportunitiesPage` desaparece (José la reemplaza
  por el Kanban de cases en el módulo 2).
- Monitor de técnicos, evidencias, firmas, PDF de attestation, invoices
  actuales: **no cambian**.

Lo que Mateo **no** tiene que hacer: la migración de datos, el retiro de
`Opportunity`, `Program`, zonas, catálogo. Todo eso es de José.

## Pendientes para cerrar antes del 28

- `assigned_technician_id`: fuera de `Case` (propuesta) o dentro.
- `funder_status_code` (propuesta) o mantener FK a `funder_statuses`.
- Qué pasa cuando falla la inspección (pregunta al cliente; mientras
  tanto `inspection_pending` → `ready_to_install`).
