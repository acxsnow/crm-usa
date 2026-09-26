# Esqueleto `Case` — diseño

Fecha: 25 de septiembre de 2026. Base: `docs/contratos/case.md` (aprobado por
Mateo), `decisiones.md` D2, D6 y D8.

Entrega a Mateo: **hoy**. Es la base sobre la que arranca su módulo 5 el 1 de
octubre.

---

## 1. Qué es esto

`Case` es **la puerta**, no la venta. Nace cuando el vendedor toca, no cuando
alguien dice que sí. El cliente aparece después, si aparece: `customer_id` es
nulo hasta que alguien abre y da sus datos, y las tres primeras etapas
(`no_contact`, `not_interested`, `not_eligible`) existen sin cliente.

Todo el flujo del PDF cuelga de esta entidad: los módulos 2 y 3 la llenan, el 4
la revisa, el 5 la instala, el 6 la cobra.

## 2. Qué se aparta del contrato aprobado

Tres divergencias. Mateo tiene que enterarse de las dos primeras.

- **`Lead` se retira.** El contrato tenía `Case.lead_id` y `source='lead'`. Ya
  no: el Case cubre la puerta desde el primer toque, así que `lead_id` no se
  crea y `source` queda en `visit | import | manual | migration`. La tabla
  `leads`, su pantalla, su importación CSV y el permiso `leads.manage` se
  retiran junto con `Opportunity` en el módulo 1.
- **Los campos de admisión no son columnas de `Case`.**
  `utility_account_number`, `meter_number`, `unit_type` y `benefit_type` son
  respuestas del formulario dinámico y varían por programa: el número de medidor
  lo pide Arizona y quizá no TECH Clean. Van a `step_submissions` (módulo 2).
  Hasta que esa tabla exista, `opportunities` los conserva.
- **Numeración de migraciones.** El contrato decía `0011`/`0012`; `0011` quedó
  tomada por `programs_read_out_of_config`. Serán `0012` y `0013`.

Y los tres pendientes que el contrato dejó abiertos, ya cerrados:

- `assigned_technician_id` **fuera** de `Case`: vive solo en `Project`, que es
  donde se agenda y se ejecuta. Tenerlo en los dos crea dos verdades.
- `funder_status_code` como **texto plano**, no FK. La tabla `funder_statuses`
  queda como catálogo de etiquetas.
- Inspección fallida: `inspection_pending → ready_to_install`, marcado en el
  código como **provisional** hasta que responda el cliente.

## 3. Tablas

### `cases`

Mixins del repo: `UUIDPKMixin`, `TimestampMixin`, `OrgScopedMixin`,
`PropertyAddressMixin`.

- Identidad: `case_number` (único por organización, formato `CASE-AAAA-NNNN`,
  generado en el service, nunca editable), `source`.
- Programa: `program_id`, `program_version_id`, `zone_id` — los tres nulos
  mientras la puerta no responde.
- Personas: `customer_id`, `assigned_salesperson_id`, `assigned_admin_id`.
- Propiedad: los campos del mixin más `normalized_address`, calculada con
  `shared/normalize.py` al guardar. Índice por
  (`organization_id`, `normalized_address`, `address_unit`) para reconocer la
  puerta repetida. **No** es unique: una propiedad puede tener un case cerrado y
  otro abierto años después. La regla "un solo case abierto por propiedad" vive
  en el service, no en la base.
- Etapa: `stage_code`, `substatus_code`, `stage_reason`.
- Programa (los llena Administración): `application_number`, `approval_code`,
  `funder_status_code`.
- Fechas hito: `first_contact_at`, `submitted_at`, `approved_at`,
  `scheduled_install_date`, `completed_at`, `closed_at`. **Solo las escribe
  `transition()`**, para que no se desincronicen del historial.

### `case_stage_events`

Historial inmutable, una fila por cada cambio de etapa o sub-estado:
`case_id`, `from_stage_code`, `to_stage_code`, `from_substatus_code`,
`to_substatus_code`, `reason`, `actor_user_id`, `occurred_at`.

Con esto se calculan días por etapa, tiempo hasta aprobación, tasa de rechazo y
productividad por zona. **Es la pieza que no se puede reconstruir después**: si
no se guarda desde el primer día, los reportes del PDF §7 quedan sin datos para
siempre.

### `programs`, `program_versions`, `program_zones`

`programs` con lo mínimo: `code`, `name`, `active`, `is_system_template`. Las
otras dos nacen vacías; las llena el módulo 1.

### `projects.case_id`

Columna nueva, nullable, con FK e índice. `projects.opportunity_id` se conserva
hasta que se retire `Opportunity`.

## 4. El motor de etapas

- `cases/stages.py` — las 15 etapas y `ALLOWED_TRANSITIONS: dict[str, set[str]]`
  con **todas** las transiciones desde el día uno, incluidas las de Mateo. Así
  él no tiene que tocar el archivo para que sus etapas funcionen.
- `transition(db, case, to_stage, actor, reason=None, substatus=None)` — valida
  la transición, ejecuta las guardas, cambia etapa y sub-estado, escribe la
  fecha hito que corresponda, inserta el `case_stage_event`, registra auditoría
  y emite `case.stage_changed`.
- `set_substatus(...)` — misma mecánica sin cambio de etapa.
- `register_guard(from_stage, to_stage, fn)` — cada cadena registra las suyas
  desde su propio paquete. Mateo no edita el archivo de José ni al revés.
- **Nadie escribe `stage_code` directamente**, con un test del repo que recorre
  `app/` y lo verifica.

## 5. `shared/events.py`

`emit(name, payload)` mínimo: registra el evento y llama a los suscriptores
en proceso. El módulo 7 (Mateo) lo reemplaza por la cola real. El objetivo hoy
es que los puntos de emisión existan y estén en su sitio, no la entrega
garantizada.

## 6. El menú, alineado al modelo

El menú actual describe el modelo que se retira. Se corrige junto con esto:

- **Sale Prospectos** — `Lead` se retira.
- **Sale Pipeline** — `Opportunity` se retira; su reemplazo es el tablero de
  cases dentro de Expedientes, en el módulo 2.
- **Documentos** queda solo para Administración (`documents.review`): al
  vendedor no le sirve una pantalla aparte, los adjuntos viven dentro del caso.
- **Expedientes** (`cases.read_own` o `cases.read_all`) y **Clientes**
  (`customers.read`) quedan como el centro del vendedor.

Las rutas `/leads` y `/opportunities` **no se borran hoy**: salen del menú y se
retiran formalmente en el módulo 1, con sus tests. "Expedientes" sigue apuntando
a `/applications` hasta que exista la pantalla de cases (módulo 2).

## 7. Migración

`0012_cases` — crea las cinco tablas y agrega `projects.case_id`. No borra nada.
`downgrade()` real.

`0013_migrate_to_cases` — **pendiente de verificar si hace falta**. Todas las
tablas de la base local están vacías (0 opportunities, 0 projects, 0
applications, 0 customers, 0 leads). Si el Render tampoco tiene datos, no se
escribe y `Opportunity` se retira en el módulo 1 como estaba planeado. Escribir
200 líneas de migración de datos que nunca se ejecutan es código no ejercitado,
que falla el día que importa.

## 8. Qué NO entra

`step_submissions`, T&C, firma, `case_documents`, el formulario dinámico y la
pantalla del vendedor. Eso es el módulo 2 y 3. Hoy se entrega la base sobre la
que Mateo arranca, no la funcionalidad del vendedor.

## 9. Pruebas

TDD en todo:

- Cada transición permitida y cada prohibida.
- Las guardas se ejecutan y bloquean.
- Las fechas hito solo las escribe `transition()`.
- `case_number` correlativo por organización y año, sin choques.
- Scope por `organization_id` en toda consulta.
- El test que impide escribir `stage_code` a mano.
- El evento se emite en cada transición.
