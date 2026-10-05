# Contrato de la Cadena B — para José

Lo que la Cadena B (Mateo: `field_ops`, `billing`, `notifications`) expone y
lo que cambió fuera de su paquete. Se actualiza con cada entrega. Detalle de
diseño: `docs/superpowers/specs/2026-09-27-modulo-5-campo-design.md` (módulo 5)
y `docs/superpowers/specs/2026-09-28-modulo-6-cobro-design.md` (módulo 6).

Última actualización: 28 de septiembre de 2026 · módulo 6 (facturación y cobro,
backend y pantallas). Lo del módulo 6 está en la sección 9.

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
| `inspection_pending → billing_in_progress` | Acta confirmada por Administración (módulo 6; antes: inspección aprobada) | — |
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

**Validación (27 sep, Postgres 16 en Docker):** sube, baja y vuelve a subir.
Comparando modelos contra la base no aparece ninguna diferencia nueva; las
únicas en estas tablas son las FK de organización que faltan desde `0003`
(COD-06, anterior al módulo).

## 7. Pendientes conocidos

- `PATCH /projects/{id}` (heredado) todavía deja cambiar `status`,
  `scheduled_date` y técnico sin pasar por los comandos. Hay que cerrarlo en el
  módulo 6 o antes: hoy permitiría marcar un proyecto `completed` sin cierre.
- Si un permiso se rechaza o vence con el expediente ya en «Listo para
  instalar», el expediente no retrocede. Falta decidir con el cliente si debe
  bloquear la instalación.
- Qué pasa con la inspección fallida sigue provisional (tu mapa): vuelve a
  «Listo para instalar».
- Pantallas: `tsc`, `vite build` y el servidor de Vite sin errores; falta la
  revisión visual en navegador.

## 8. Lo que encontró el recorrido de punta a punta (27 sep)

Recorrido completo por la API real con un usuario por rol (vendedor →
Administración → técnico → inspección fallida → re-trabajo → aprobada). Destapó
dos errores que las pruebas unitarias no veían, ya corregidos con su prueba:

- **Zona horaria:** "hoy" se calculaba con el reloj del servidor (UTC). Desde
  las 7 p. m. en Bogotá (5 p. m. en Phoenix), agendar la instalación del día
  daba "fecha pasada" y el cierre quedaba con la fecha de mañana. Ahora las
  fechas de negocio usan `organizations.timezone` (`field_ops/clock.py`), y el
  frontend usa la fecha local del navegador. **Ojo, José:** el mismo patrón
  (`date.today()`) está en `billing/service.py` (vencimiento de facturas); es
  mío y lo corrijo en el módulo 6. **Corregido en el módulo 6** (COD-10).
- **Plantilla por defecto:** se busca por nombre, y las organizaciones que ya
  tenían la plantilla anterior nunca recibían la del §8. La nueva tiene nombre
  propio; los proyectos anteriores conservan su copia.

---

## 9. Módulo 6 — facturación y cobro (28 sep)

### 9.1 Pedido a José: dos transiciones en `cases/stages.py`

Solo agregadas; el código de la Cadena B ya las usa en cuanto existan.

1. **`approved → ready_to_install`**: instalar antes de tener el permiso, como se
   trabaja en la práctica (el cliente lo confirmó). Permiso sugerido: el de
   liberar la orden (`dispatch.manage`). `schedule_installation` ya intenta esa
   transición; hoy no existe y el expediente sigue el camino por "Permiso en
   trámite".
2. **`installed → billing_in_progress`**: cobrar a un programa que no exige
   inspección (TECH, este año solo pide el número de permiso). Hoy el cobro se
   crea igual, pero el expediente se queda en "Instalado" hasta que la
   transición exista. Las guardas para ese salto ya se registran solas si
   `stages.is_allowed` la encuentra.

### 9.2 Lo que toqué fuera de mi paquete

- **`app/main.py`**: dos líneas nuevas que registran `billing/case_hooks.py`,
  junto a las de campo.
- **`shared/permissions.py`**: permisos nuevos `billing.configure` (Administrador
  y Contabilidad) y `quotes.manage` (Administrador, Administración y
  Contabilidad). La migración los agrega a los roles de cada organización.
- **`api/v1/router.py`** y **`frontend/src/app/router.tsx`**: solo líneas nuevas.
- **Programas**: la configuración de cobro apunta a tu `Program` y no lo
  modifica. Mientras llega tu módulo 1, en local creé los programas demo
  directo en la base.
- **Cotizaciones en `/billing/quotes`**, no en `/quotes`: tu prueba de COD-01
  exige que la ruta del CRM retirado no responda, y así se queda.

### 9.3 Cómo mueve el cobro el expediente

Mismo mecanismo que campo: los hechos del cobro llaman a `advance_case()` y
`mark_substatus()` (`billing/claims.py`, `_sync_case`).

| Hecho | Expediente |
|---|---|
| Primer cobro creado | → "En proceso de cobro", sub-estado `invoice_pending` |
| Radicado | sub-estado `submitted` |
| Rechazado por el programa | sub-estado `rejected_by_program` (manda sobre los demás) |
| Todos los cobros vivos pagados | → "Pagado" (necesita `invoices.record_payment`) |
| Cobro nuevo sobre un expediente "Pagado" | No retrocede |
| Trabajo particular (cotización, factura, pagos) | Nunca mueve el expediente |

Guardas nuevas (`billing/case_hooks.py`), también para tu ruta manual:

| Transición | Guarda |
|---|---|
| `inspection_pending`/`installed → billing_in_progress` | Al menos un cobro de programa vivo (además del acta confirmada de campo) |
| `billing_in_progress → paid` | Todos los cobros vivos pagados |

El requisito automático "Aprobación del programa con código" lee
`cases.approved_at` y `cases.approval_code`. Si tu flujo de aprobación no llena
`approval_code`, ningún cobro se puede radicar (lo encontró el recorrido:
los expedientes demo no lo tienen). T&C y documentos quedan como requisitos
manuales hasta que termines los módulos 2 y 3; entonces pasan a automáticos.

### 9.4 Eventos (después del commit)

| Evento | Datos |
|---|---|
| `project.technician_info_confirmed` | `project_id`, `organization_id` |
| `project.returned_to_technician` | `project_id`, `organization_id`, `reason` |
| `claim.created` / `claim.submitted` / `claim.withdrawn` | `claim_id`, `project_id`, `program_id`, `organization_id` |
| `claim.rejected` | lo anterior + `category` |
| `claim.paid` | lo anterior + `amount` |
| `quote.sent` / `quote.accepted` | `quote_id`, `quote_number`, `version`, `organization_id` (+ `invoice_id`) |

### 9.5 API nueva

| Método y ruta | Permiso |
|---|---|
| `POST /projects/{id}/review/confirm`, `/review/return`; `GET /projects/{id}/reviews` | `checklists.approve` / lectura |
| `POST /inspections/{id}/signed-permit` | `inspections.manage` |
| `GET/PUT /billing/programs/{id}/profile`, `…/rates`, `…/jurisdictions`, `…/requirements` | `invoices.read` / `billing.configure` |
| `GET /projects/{id}/billing/eligibility` | `invoices.read` |
| `POST /projects/{id}/claims`; `GET /claims`, `GET /claims/{id}` | `billing.submit` / `invoices.read` |
| `POST/DELETE /claims/{id}/checks/{code}`; `POST /claims/{id}/submit`, `/reject`, `/withdraw`, `/invoice/reissue` | `billing.submit` |
| `POST /claims/{id}/payment` | `invoices.record_payment` |
| `GET /billing/dashboard` | `invoices.read` |
| `GET /invoices/{id}/pdf`, `POST /invoices/preview` | `invoices.read` |
| `PUT /invoices/{id}/lines` (borrador), `POST /invoices/{id}/issue`, `POST /invoices/{id}/void` | `invoices.update` / `invoices.create` |
| `GET/POST /billing/quotes`, `GET/PATCH /billing/quotes/{id}`, `/send`, `/revise`, `/accept`, `/reject` | `quotes.manage` |

Reglas de campo que cambiaron: agendar la inspección exige un permiso
radicado; aprobarla exige el permiso firmado por el inspector (categoría de
evidencia nueva `permit_signed`, ya son 16); un acta devuelta al técnico se
vuelve a cerrar aunque el expediente esté más adelante.

### 9.6 Esquema — migración `0015_billing_module6`

`invoices`: `kind`, `case_id`, `claim_id`, `quote_id`, `replaces_invoice_id`,
`document_status` (el enum `invoice_status` pasa a texto; el estado de pago se
calcula de los pagos), `project_id` opcional, dinero en `Numeric`. Tablas
nuevas: `invoice_lines`, `document_sequences`, `billing_program_profiles`,
`program_rebate_rates`, `program_jurisdictions`, `program_claim_requirements`,
`project_reviews`, `rebate_claims` (índice único parcial por proyecto y
programa, salvo retirados), `rebate_claim_attempts`, `rebate_claim_checks`,
`quotes`, `quote_lines`. Si integras antes otra `0015`, la renumero yo.

**Validación (28 sep, Postgres 16 en Docker):** sube, baja y vuelve a subir;
sin diferencias nuevas entre modelos y base (solo las FK de organización de
COD-06).

### 9.7 Recorrido de punta a punta (28 sep, API real)

Instalación en Phoenix con dos programas: LADWP radicado; Eficiencia de Arizona
rechazado por motivo técnico → acta devuelta al técnico (el expediente se
quedó en cobro) → reintento bloqueado por el checklist → el técnico corrige y
cierra → Administración confirma → se radica de nuevo (el rechazo queda en el
historial) → Arizona pagado (el expediente sigue en cobro) → LADWP paga $150
menos (diferencia visible) → expediente "Pagado". Trabajo particular:
cotización v1, ajuste v2, aceptada, factura emitida `FAC-2026-0001`, pago
parcial y saldo → pagada sin tocar el expediente. PDF de todas las facturas.

### 9.8 Pendientes del módulo 6

- ~~Las dos transiciones de 9.1 (tuyas).~~ **Cerrado el 4 oct 2026** (Mateo,
  cubriendo la Cadena A): `approved → ready_to_install` e `installed →
  billing_in_progress` están en `stages.py`; las guardas de campo se registran
  solas y la prueba que se saltaba (`test_field_reviews.py`) ya corre.
- ~~Catálogo de programas (tu módulo 1).~~ **Cerrado el 4 oct 2026**: pantalla
  «Configuración de programas» (`/programs`), con entidad que factura por
  programa (`Program.invoice_entity`, informativo; el emisor del PDF sigue en
  la configuración de cobro del programa).
- Checklist de instalación por programa (pendiente del módulo 5): **cerrado el
  4 oct 2026**, pantalla `/checklists` y `PUT`/`DELETE /checklist-templates/{id}`;
  un programa tiene a lo sumo una plantilla.
- GPS real en el celular (pendiente del módulo 5): **habilitado el 4 oct 2026**
  con HTTPS de desarrollo (`frontend/scripts/dev-cert.sh` + `DEV_HTTPS=1`, ver
  README). Falta la prueba en campo con un teléfono.
- Confirmar con el cliente: qué entidad factura cada programa (Delta HVAC
  Service Inc. o Desert Alliance Properties LLC) y si el PDF va en inglés (hoy
  sí).
- Plantillas propias por programa (GoZero/HousecallPro, pedestal/Charge Ready,
  del cronograma): el spec las dejó en dos plantillas con los datos y el texto
  legal por programa; si un programa exige su formato, se agrega como otra.
- ~~`PATCH /projects/{id}` heredado (sección 7).~~ **Cerrado el 4 oct 2026**:
  solo edita título y notas; estado, fechas y técnico van por sus comandos.
