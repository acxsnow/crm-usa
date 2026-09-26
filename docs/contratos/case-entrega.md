# Entrega del esqueleto `Case` — para Mateo

25 de septiembre de 2026. Rama `cadenaA`. Migración `0012`.

Esto es lo que quedó listo para que arranques el módulo 5 el 1 de octubre. Va
contra `docs/contratos/case.md`, que ya revisaste, con tres cambios que están
señalados abajo.

---

## 1. Lo que puedes usar desde ya

### Tablas

- `cases` — el expediente.
- `case_stage_events` — el historial inmutable de cambios de etapa.
- `programs`, `program_versions`, `program_zones` — mínimas. Las dos últimas
  nacen vacías; las lleno yo en el módulo 1.
- `projects.case_id` — nullable, con FK e índice. **Es tu punto de enganche.**
  `projects.opportunity_id` se queda hasta que retire `Opportunity`, así que no
  tienes que cambiar nada de golpe.

### Código

- `app/modules/cases/models.py` — las entidades.
- `app/modules/cases/stages.py` — las 15 etapas y `ALLOWED_TRANSITIONS`, con
  **todas** las transiciones, incluidas las tuyas. No tienes que editar este
  archivo para que tus etapas funcionen.
- `app/modules/cases/service.py` — `create_case`, `transition`, `set_substatus`,
  `get_case_or_404`, `list_stage_events`.
- `app/shared/events.py` — `emit()` y `subscribe()`.
- `app/modules/cases/router.py` y `schemas.py` — la API.

### API

- `GET /api/v1/cases/stages` — el mapa completo del flujo: código, etiqueta en
  español, si es inicial, sus sub-estados y a qué etapas puede pasar. **Úsalo en
  vez de repetir los códigos en el frontend.**
- `GET /api/v1/cases` — listado. `cases.read_all` ve todos; `cases.read_own`
  solo los propios, y el filtro va en la consulta. Acepta `?stage_code=`, `?q=`,
  `?limit=&offset=`, y devuelve `X-Total-Count`.
- `POST /api/v1/cases` — abre el expediente de una puerta (`cases.create`).
- `GET /api/v1/cases/{id}` y `GET /api/v1/cases/{id}/events` — detalle e
  historial.
- `POST /api/v1/cases/{id}/transition` — mueve de etapa.
- `POST /api/v1/cases/{id}/substatus` — cambia el sub-estado sin mover de etapa.

Un expediente ajeno responde **404, no 403**, tanto si es de otra organización
como si es de otro vendedor: un 403 confirmaría que existe.

## 2. Cómo mover un expediente de etapa

```python
from app.modules.cases import service as case_service

await case_service.transition(
    db, case=case, to_stage="ready_to_install", actor_id=current_user.id,
    reason="Permiso aprobado por la ciudad",
)
```

`transition()` valida contra el mapa, corre las guardas, cambia la etapa,
escribe la fecha hito, inserta el historial, audita y emite el evento. Si la
transición no existe, lanza `InvalidInputError` y no toca nada.

**Nadie escribe `stage_code` directamente.** Hay un test que recorre `app/` y
falla si algún archivo fuera de `cases/service.py` lo asigna. La razón:
`case_stage_events` es la única fuente de los reportes de tiempos del PDF §7 y
**no se puede reconstruir después**.

## 3. Cómo registrar tus reglas de negocio

Una guarda bloquea una transición. Se registra desde tu propio paquete, al
importarse — no tocas mi archivo ni yo el tuyo:

```python
# app/modules/field_ops/guards.py
from app.modules.cases import stages
from app.shared.errors import InvalidInputError

def checklist_completo(*, db, case, actor_id, reason):
    if not ...:
        raise InvalidInputError(
            "El checklist técnico no está completo.", code="checklist_incomplete"
        )

stages.register_guard("ready_to_install", "installed", checklist_completo)
```

`register_guard` lanza `KeyError` si registras una guarda para una transición
que no existe en el mapa — así un error de escritura no se queda callado.

## 4. Tus tramos del flujo

Ya están en `ALLOWED_TRANSITIONS`:

- **Módulo 4:** `pending_approval` → `approved` | `rejected` | `on_hold`;
  `on_hold` → `approved` | `rejected`; `rejected` → `pending_approval`.
- **Módulo 5:** `approved` → `permit_in_progress` → `ready_to_install` →
  `installed` → `inspection_pending` → `billing_in_progress`.
- **Módulo 6:** `billing_in_progress` → `paid` → `closed`.
- Cualquier etapa → `closed` (cierre administrativo).

Sub-estados disponibles, en `stages.SUBSTATUSES`: los de `pending_approval`
(`pending_review`, `returned`, `ready_to_submit`, `submitted_to_program`,
`program_review`), `install_scheduled`, `inspection_approved`, y los de cobro
(`invoice_pending`, `submitted`, `rejected_by_program`).

**Ojo con la devolución:** `returned` es un **sub-estado**, no una etapa. Cuando
devuelves un expediente al vendedor, la etapa sigue siendo `pending_approval` y
usas `set_substatus()`. Si retrocediera a `new_prospect`, el contador de días de
aprobación se reiniciaría y el reporte de tiempos mentiría.

## 5. Eventos

Cada transición emite `case.stage_changed` con `case_id`, `case_number`,
`from_stage`, `to_stage` y `reason`. También hay `case.created` y
`case.substatus_changed`.

Hoy `emit()` es en proceso y síncrono: **no es una cola**. Existe para que los
puntos de emisión estén en su sitio desde el principio. Cuando montes el módulo
7 lo reemplazas por Celery/Redis y la firma no cambia, así que los emisores no se
tocan. Un suscriptor que falla no deshace la transición.

## 6. Los tres cambios respecto al contrato

**1. `Lead` se retira.** El contrato tenía `Case.lead_id` y `source='lead'`. Ya
no existen: el expediente cubre la puerta desde el primer toque, así que un
prospecto y un expediente eran la misma cosa con dos nombres. `source` queda en
`visit | import | manual | migration`. La tabla `leads`, su pantalla y su
importación CSV se retiran conmigo en el módulo 1. **Esto no estaba en lo que
aprobaste** — si te rompe algo, dime hoy.

**2. Los campos de admisión no son columnas de `Case`.**
`utility_account_number`, `meter_number`, `unit_type` y `benefit_type` son
respuestas del formulario dinámico y varían por programa, así que van a
`step_submissions` (mi módulo 2). Hasta entonces `opportunities` los conserva.

**3. Numeración de migraciones.** El contrato decía `0011`/`0012`; `0011` quedó
tomada. El esqueleto es `0012`.

Y los tres pendientes que habías dejado abiertos, ya cerrados como proponías:

- `assigned_technician_id` **fuera** de `Case`: es tuyo, vive en `Project`. Si
  el tablero lo necesita, se expone calculado.
- `funder_status_code` como texto plano. `funder_statuses` queda de catálogo.
- Inspección fallida: `inspection_pending → ready_to_install`, **provisional**
  hasta que responda el cliente. Está marcado así en el código.

## 7. Lo que NO está

- **La migración de datos (`0013`).** Todas las tablas están vacías: 0
  opportunities, 0 projects, 0 applications, 0 customers, 0 leads. No la escribí
  porque no movería nada, y una migración que nunca se ejecuta es código sin
  probar. **Si el Render tiene datos, avísame y la escribo.**
- `step_submissions`, T&C, firma, `case_documents` y el formulario dinámico:
  mis módulos 2 y 3.
- La pantalla de expedientes. El menú ya dice "Expedientes" pero todavía apunta
  a `/applications`.

## 8. Cambios en el menú

Quité **Prospectos** y **Pipeline**: pertenecen al modelo que se retira.
**Documentos** quedó solo para quien revisa (`documents.review`), porque al
vendedor no le sirve una pantalla aparte — sus adjuntos van dentro del
expediente.

Las rutas `/leads` y `/opportunities` **no las borré**, solo salieron del menú.
El retiro formal, con sus tests, va en mi módulo 1.

Qué ve cada rol: `docs/menu-por-rol.md`.

## 9. Verificación

- `pytest -q` → **209 passed**. 51 nuevos: 18 del mapa de etapas, 19 del
  servicio y 14 de la API.
- `tsc -b && vite build` → limpio.
- Migración `0012` probada de ida, de vuelta y de ida otra vez contra Postgres.
- Menú verificado en navegador con los seis roles.

## 10. Una limitación que debes conocer

`normalize_address` no expande abreviaturas: **"123 Main St" y "123 Main Street"
son dos puertas distintas**. En venta puerta a puerta es la variación más común,
así que hoy un vendedor puede abrir un segundo expediente para una casa que ya
tenía uno. No lo arreglé porque esa función la comparten `Lead`, `Opportunity` y
`Customer` y cambiarla afectaría la deduplicación de todos. Lo resuelvo en el
módulo 2, con la pantalla del vendedor, que además puede avisar "esta puerta ya
tiene expediente" antes de guardar. Hay un test que documenta el comportamiento
actual y que fallará el día que se arregle.

---

## Referencias

- `docs/contratos/case.md` — el contrato que acordamos.
- `docs/superpowers/specs/2026-09-25-esqueleto-case-design.md` — el diseño.
- `docs/menu-por-rol.md` — qué ve cada rol.
- `docs/MODULO-0-GUIA-TECNICA.md` — cómo se agrega o quita algo del menú.
