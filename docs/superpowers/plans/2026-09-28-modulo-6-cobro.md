# Módulo 6 — Facturación y cobro — Plan de implementación

> **Para agentes:** se ejecuta en la sesión con superpowers:executing-plans (modo nativo). Pasos con casillas `- [ ]`.

**Goal:** Cobro de rebates por programa (varios por instalación, con tarifa y jurisdicción vigentes, checklist de radicación, rechazo y reintento) y trabajo particular (cotización → factura → pagos), sobre el expediente.

**Architecture:** Paquete `billing` reorganizado por responsabilidad: `money.py` y `numbering.py` (base), `program_config.py` (tarifas, jurisdicciones, requisitos), `claims.py` + `requirements.py` (cobro de rebate), `quotes.py` e `invoices.py` (particular y documento común), `pdf.py`, `dashboard.py`. El expediente se mueve con `field_ops.case_flow.advance_case()` y guardas async en `billing/case_hooks.py`. En el paquete de José solo cambian dos líneas del mapa de etapas, pedidas y avisadas (spec §9).

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest + SQLite en memoria, ReportLab; React 18 + TypeScript + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-09-28-modulo-6-cobro-design.md`

## Global Constraints

- Dinero siempre `Decimal` y `Numeric(12,2)`; ningún `float` en `billing`. Redondeo `ROUND_HALF_UP` a centavos.
- Mensajes en español con las excepciones de `app/shared/errors.py`; nada de `HTTPException` en código nuevo.
- Toda consulta filtrada por `organization_id` del token; ajeno → 404.
- Fechas de negocio con `field_ops.clock.org_today()`.
- Una factura emitida no se edita: se anula y se emite otra que la reemplaza.
- Los servicios que mueven el expediente no hacen commit antes de `advance_case()`.
- Eventos con `app.shared.events.emit` solo después del commit.
- Archivos compartidos (`shared/permissions.py`, `api/v1/router.py`, `router.tsx`, `navigation.ts`): solo líneas nuevas.
- Sin commits hasta que Mateo lo pida. Verificación: `cd backend && .venv/bin/python -m pytest -q`; `cd frontend && npm run build`.

## Review Focus

- Dos cobros del mismo programa creados a la vez → uno 409, nunca dos.
- Tarifa con vigencias solapadas o una instalación sin tarifa vigente → mensaje claro, no un 500.
- Pago que no coincide con la tarifa (menos o más) → se registra y la diferencia queda visible.
- Cobro de un programa cuando el expediente ya está "Pagado" → se crea y no hace retroceder la etapa.
- Técnico con el acta devuelta mientras el expediente está en cobro → puede corregir y volver a cerrar.

---

## Fase 1 — Base

### Task 1: Dinero y numeración segura

**Files:** Create `backend/app/modules/billing/money.py`, `backend/app/modules/billing/numbering.py`; Test `backend/tests/test_billing_base.py`.

**Interfaces — Produces:** `to_money(value) -> Decimal`, `money_sum(values) -> Decimal`; `async def next_number(db, *, organization_id, series: str, year: int) -> str` → `"REB-2026-0001"`; modelo `DocumentSequence`.

- [x] Pruebas: `to_money("10.005") == Decimal("10.01")`; `money_sum` de 0.1 tres veces es `0.30` exacto; `next_number` correlativo por serie y año; series distintas no chocan; dos organizaciones no chocan; año nuevo reinicia.
- [x] Implementar; `DocumentSequence` con restricción única (org, serie, año) y `with_for_update()`.

### Task 2: Factura sobre el expediente, con líneas

**Files:** Modify `billing/models.py`, `billing/service.py`, `billing/schemas.py`, `billing/router.py`, `tests/test_billing.py`; Create migración `0015_billing_module6.py` (parte 1: invoices, lines, sequences).

**Interfaces — Produces:** `Invoice.kind`, `case_id`, `claim_id`, `quote_id`, `replaces_invoice_id`, `document_status` (`draft|issued|void`), `payment_status` (derivado), `total` (suma de líneas), `balance`; `InvoiceLine`.

- [x] Pruebas: los pagos suman en `Decimal`; el estado de pago sale de los pagos (`unpaid|partial|paid`); vencida según la fecha de la organización (COD-10); mensajes en español; las pruebas heredadas siguen verdes adaptadas.
- [x] Migración: enum `invoice_status` → texto; datos viejos: `pending|sent|overdue` → `issued`, `paid` → `issued` (el pago lo dicen los pagos), `cancelled` → `void`; `project_id` opcional. Validar con `--sql` y contra Postgres.

## Fase 2 — Configuración de cobro por programa

### Task 3: Tarifas, jurisdicciones, requisitos y perfil

**Files:** Create `billing/program_config.py`, `billing/requirements.py` (catálogo de reglas automáticas), rutas en `billing/router.py`; permisos `billing.configure` y `quotes.manage` en `shared/permissions.py` (solo líneas nuevas) y su migración de catálogo; Test `tests/test_billing_program_config.py`.

**Interfaces — Produces:** `rate_for(db, program_id, on: date) -> ProgramRebateRate | None`; `programs_for_address(db, org, *, city, zip, on) -> list[Program]`; `default_requirements() -> list[dict]`; `AUTO_RULES: dict[str, callable]`.

- [x] Pruebas: tarifa vigente por fecha; solapamiento → 400; sin tarifa vigente → `None`; jurisdicción por ciudad y por código postal normalizados, respetando vigencia; perfil nuevo siembra los requisitos por defecto (proceso real + permiso aprobado + inspección aprobada); desactivar "inspección" en un programa; solo `billing.configure` edita (403 para Administración); aislamiento por organización.

## Fase 3 — Ajuste del módulo 5

### Task 4: Permiso flexible, inspección con permiso firmado, confirmación del acta

**Files:** Modify `field_ops/inspections.py`, `field_ops/guards.py`, `field_ops/installation.py`, `field_ops/catalogs.py` (categoría `permit_signed`), `field_ops/case_hooks.py`; Create `field_ops/reviews.py`; migración (parte 2: `project_reviews`); Test `tests/test_field_reviews.py` y ajustes en las pruebas de campo.

**Interfaces — Produces:** `confirm_technician_info(...)`, `return_to_technician(...)`, `is_technician_info_confirmed(db, project) -> bool`.

- [x] Pruebas: agendar inspección sin permiso radicado → 409; aprobar inspección sin foto `permit_signed` → 400; confirmar el acta (`checklists.approve`) y devolverla con motivo (reabre: proyecto `scheduled`, checklist editable); el técnico vuelve a cerrar con el expediente en `billing_in_progress`; historial de revisiones; el técnico no puede confirmar su propia acta (403).
- [x] Guarda de entrada a cobro: pasa de "inspección aprobada" a "acta confirmada" (la inspección queda como requisito del programa).
- [x] (pendiente de José: la transición aún no existe; `schedule_installation` ya la intenta; prueba en `test_field_reviews.py`, se salta sola hasta que exista) Si José ya agregó `approved → ready_to_install`: prueba de liberar la orden sin permiso. Si no, queda anotado y la prueba se marca `skip` con el motivo.

## Fase 4 — Cobro de rebate

### Task 5: Elegibilidad y creación del cobro

**Files:** Create `billing/claims.py`; modelos `RebateClaim`, `RebateClaimAttempt`, `RebateClaimCheck`; migración (parte 3); Test `tests/test_billing_claims.py`.

**Interfaces — Produces:** `eligibility(db, *, project) -> list[{program, applies, rate, reason}]`; `create_claim(db, *, org, user, project_id, program_id, override_reason=None) -> RebateClaim` (crea la factura de rebate emitida con la tarifa congelada y mueve el expediente a `billing_in_progress`).

- [x] Pruebas: sugiere solo los que aplican en la fecha de instalación; tarifa de diciembre aunque se cree en enero; no aplica sin motivo → 400, con motivo → creado; segundo cobro del mismo programa → 409; retirado libera; instalación sin acta confirmada → 409; expediente pasa a "En proceso de cobro / factura pendiente"; expediente ya pagado → se crea y no retrocede.

### Task 6: Checklist, radicar, rechazar, pagar, retirar, refacturar

**Files:** `billing/claims.py`, `billing/requirements.py`, `billing/case_hooks.py` (guardas y efectos), rutas; Test `tests/test_billing_claims.py`.

**Interfaces — Produces:** `evaluate_requirements(db, claim) -> list[{code, label, kind, met, detail}]`; `confirm_manual_check`, `submit_claim`, `reject_claim`, `record_claim_payment`, `withdraw_claim`, `reissue_invoice`.

- [x] Pruebas: radicar con pendientes → 400 con la lista; radicar completo → intento + sub-estado `submitted` + evento; rechazo exige motivo, sub-estado `rejected_by_program`, intento conservado, reintento permitido; rechazo técnico devuelve el acta; pago registra diferencia si no coincide; todos pagados → expediente "Pagado"; uno pagado y otro no → sigue en cobro; refacturar anula y reemplaza; la guarda `paid` bloquea el camino manual con cobros pendientes; permisos (`billing.submit`, `invoices.record_payment`).

## Fase 5 — Factura PDF

### Task 7: Plantillas rebate y particular, vista previa

**Files:** Create `billing/pdf.py`; rutas `GET /invoices/{id}/pdf`, `POST /invoices/preview`; Test `tests/test_billing_pdf.py`.

- [x] Pruebas: el PDF de rebate trae programa, dirección, equipos del módulo 5, rebate y balance 0; el particular trae líneas, pagos y balance; la vista previa no guarda nada ni consume número; entidad y texto legal salen del perfil del programa.

## Fase 6 — Trabajo particular

### Task 8: Cotización con versiones → factura → pagos

**Files:** Create `billing/quotes.py`; modelos `Quote`, `QuoteLine`; migración (parte 4); rutas; Test `tests/test_billing_quotes.py`.

- [x] Pruebas: numeración `COT-`; revisar crea la versión siguiente y conserva la anterior; aceptar crea la factura particular en borrador con las mismas líneas; emitir asigna `FAC-` y congela; pagos parciales y balance real; vencida por fecha de la organización; nunca mueve el expediente; `quotes.manage` requerido.

## Fase 7 — Tablero y pantallas

### Task 9: Tablero de cobros (backend)

**Files:** Create `billing/dashboard.py`; ruta `GET /billing/dashboard`; Test `tests/test_billing_dashboard.py`.

- [x] Pruebas: "por radicar" con alerta desde el día siguiente; radicados con días y alerta por umbral del programa; rechazados con días; pagado del mes y esperado por programa; particular vencidas.

### Task 10: Frontend

**Files:** `frontend/src/features/billing/*` (bandeja, detalle, configuración, cotizaciones), pasos "Confirmación" y "Cobro" en el acta (`features/field-ops/components`), tipos y API, menú.

- [x] `npm run build` limpio; revisión con capturas en escritorio y celular, como en el módulo 5.

## Fase 8 — Cierre

### Task 11: Recorrido y documentación

- [x] Recorrido de punta a punta contra la app real: instalación en Mission Hills cobrada a LADWP y TECH; rechazo técnico, devolución al técnico, corrección, reintento, pagos, expediente "Pagado"; trabajo particular cotizado, ajustado, facturado y pagado.
- [x] `docs/contratos-cadena-b.md` con lo del módulo 6 y el pedido a José; `CLAUDE.md` solo si cambia algo que otra sesión deba saber; resumen para el artefacto.
