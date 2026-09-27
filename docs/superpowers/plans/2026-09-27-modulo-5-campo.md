# Módulo 5 — Campo — Plan de implementación

> **Para agentes:** ejecutado en la sesión con superpowers:executing-plans (modo nativo). Pasos con casillas `- [ ]`.

**Goal:** Tramo de campo del expediente (`approved` → `inspection_pending`) con checklist configurable, evidencias por categoría, permisos, inspección, equipos, materiales y agenda.

**Architecture:** Los comandos de `field_ops` registran hechos y mueven el expediente con `advance_case()` (un solo punto, `field_ops/case_flow.py`); las guardas asíncronas registradas en `case_hooks.register()` protegen el camino manual. Todo el paquete nuevo vive en `field_ops`; en el de José solo cambia la llamada a la guarda (COD-08).

**Tech Stack:** FastAPI, SQLAlchemy 2 async, Alembic, pytest + SQLite en memoria; React 18 + TypeScript + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-09-27-modulo-5-campo-design.md`

## Global Constraints

- Mensajes al usuario en español, con `InvalidInputError`, `NotFoundError`, `ForbiddenError`, `ConflictError` de `app/shared/errors.py` (nunca `HTTPException` en código nuevo).
- Toda consulta filtrada por `organization_id` del token; recurso ajeno → 404.
- Nadie escribe `stage_code`: solo `cases.service.transition()` / `set_substatus()`.
- Los servicios que llaman a `transition()` no hacen commit antes: el hecho y el cambio de etapa se guardan juntos.
- Eventos con `app.shared.events.emit` solo después del commit.
- Sin líneas `Co-Authored-By` en los commits.
- Verificación antes de cada commit: `cd backend && .venv/bin/python -m pytest -q`; frontend `npm run build`.

## Review Focus

- Técnico sin proyecto asignado intentando cerrar o registrar equipos de otro → 404, nunca 403 ni éxito.
- Usuario con el permiso del hecho pero no el de la etapa siguiente (p. ej. `permits.manage` sin `dispatch.manage`) → el hecho se guarda, el expediente no avanza, sin error.
- Proyecto heredado sin `case_id` → los comandos funcionan y simplemente no mueven ningún expediente.
- Permiso aprobado con `expires_on` en el pasado → no cuenta como despejado.
- Doble inspección pendiente o resultado registrado dos veces → 409.

---

### Task 1: Infraestructura común — `shared/files` y guardas asíncronas

**Files:**
- Create: `backend/app/shared/files/__init__.py`, `backend/app/shared/files/storage.py` (movido), `backend/app/shared/files/watermark.py` (movido)
- Delete: `backend/app/modules/field_ops/storage.py`, `backend/app/modules/field_ops/watermark.py`
- Modify: importadores en `field_ops/service.py`, `field_ops/router.py`, `field_ops/pdf.py`, `billing/router.py`, `crm/router.py`, `tests/conftest.py`, `tests/test_security_hardening.py`
- Modify: `backend/app/modules/cases/service.py` (llamada a guardas)
- Test: `backend/tests/test_field_flow_guards.py`

**Interfaces:**
- Produces: `app.shared.files.storage.save_bytes/absolute_path`, `app.shared.files.watermark.*` (mismas firmas); guardas `async def fn(*, db, case, actor_id, reason)` admitidas por `register_guard`.

- [ ] Test: `test_an_async_guard_can_query_the_database_and_block` (registra una guarda async que consulta y lanza) → falla con "coroutine was never awaited".
- [ ] En `transition()`: `resultado = guard(...)`; `if inspect.isawaitable(resultado): await resultado`.
- [ ] `git mv` de los dos módulos; actualizar importadores; `pytest -q` completo en verde.
- [ ] Commit `refactor(files): mueve storage y watermark a shared/files; guardas asíncronas (COD-08)`.

### Task 2: Catálogos, esquema y migración

**Files:**
- Create: `backend/app/modules/field_ops/catalogs.py`, `backend/alembic/versions/0014_field_ops_module5.py`
- Modify: `backend/app/modules/field_ops/models.py`
- Test: `backend/tests/test_field_catalogs.py`

**Interfaces:**
- Produces: `EVIDENCE_CATEGORIES: dict[str, str]`, `INSTALLATION_CONDITIONS: dict[str, str]`, `EQUIPMENT_TYPES: dict[str, str]`; modelos `Permit`, `Inspection`, `InstalledEquipment`, `ProjectMaterial`; `PermitStatus`, `InspectionResult`; `Permit.is_cleared` (property), `ProjectChecklistItem.counts_as_required(conditions: list[str]) -> bool`, `ProjectChecklistItem.is_resolved` (property).

- [ ] Tests: las 15 categorías del §7.1 con etiqueta; `counts_as_required` con y sin condición; `is_cleared` para aprobado vigente, aprobado vencido, `not_required`, `submitted`.
- [ ] Modelos y catálogos; `Evidence.category` a `String(40)`.
- [ ] Migración con `downgrade()`; probar `alembic upgrade head` / `downgrade -1` contra Postgres si está disponible, si no dejarlo "Por verificar".
- [ ] Commit `feat(field_ops): esquema del módulo 5 y catálogos de campo`.

### Task 3: Checklist configurable y evidencias por categoría

**Files:**
- Create: `backend/app/modules/field_ops/checklist.py`
- Modify: `field_ops/service.py` (`auto_create_project_from_case` elige plantilla por programa; `upload_evidence` valida categoría), `field_ops/defaults.py` (secciones, categorías y condiciones del §8), `field_ops/router.py`, `field_ops/schemas.py`
- Test: `backend/tests/test_field_checklist.py`

**Interfaces:**
- Consumes: catálogos y modelos de Task 2.
- Produces: `async def update_checklist_item(db, *, organization_id, actor, item_id, is_complete: bool | None, not_applicable: bool | None, reason: str | None) -> ProjectChecklistItem`; `async def set_installation_conditions(db, *, organization_id, actor, project_id, conditions: list[str]) -> Project`; `async def checklist_gaps(db, project) -> list[str]` (etiquetas de lo que falta); `async def get_visible_project(db, *, organization_id, user, project_id) -> Project`.

- [ ] Tests: técnico asignado completa ítem (200) y uno no asignado recibe 404; "No aplica" sin motivo → 400; en ítem que no lo admite → 400; ítem condicional no cuenta si la condición no aplica; condición desconocida → 400; plantilla del programa elegida al aprobar; evidencia con categoría distinta a la del ítem → 400; categoría fuera de catálogo → 400.
- [ ] Implementación; rutas `PATCH /checklist-items/{id}` y `PATCH /projects/{id}/conditions`.
- [ ] Commit `feat(field_ops): checklist por programa con condiciones y No aplica`.

### Task 4: `advance_case`, permisos municipales y guardas del permiso

**Files:**
- Create: `backend/app/modules/field_ops/case_flow.py`, `backend/app/modules/field_ops/permits.py`
- Modify: `field_ops/case_hooks.py` (registra guardas), `router.py`, `schemas.py`
- Test: `backend/tests/test_field_permits.py`

**Interfaces:**
- Produces: `async def advance_case(db, *, project, to_stage, actor_id, actor_permissions, reason=None) -> bool` (True si movió); `async def case_for_project(db, project) -> Case | None`; `async def record_permit(...)`, `async def update_permit(...)`; guardas `guard_has_permit`, `guard_permits_cleared`.

- [ ] Tests: registrar el primer permiso mueve `approved → permit_in_progress`; aprobarlo mueve a `ready_to_install`; con dos permisos, uno pendiente no mueve; vencido no despeja; `not_required` sin motivo → 400; usuario con `permits.manage` sin `dispatch.manage` guarda pero no avanza; guarda bloquea el paso manual por `/cases/{id}/transition` sin permiso registrado; proyecto sin expediente funciona.
- [ ] Commit `feat(field_ops): permisos municipales que mueven el expediente`.

### Task 5: Equipos, materiales, agenda y cierre de instalación

**Files:**
- Create: `backend/app/modules/field_ops/installation.py`
- Modify: `case_hooks.py`, `router.py`, `schemas.py`
- Test: `backend/tests/test_field_installation.py`

**Interfaces:**
- Produces: `add_equipment`, `delete_equipment`, `add_material`, `delete_material`, `schedule_installation`, `close_installation`, `list_agenda`; guarda `guard_installation_complete`.

- [ ] Tests: agendar marca `install_scheduled` y emite `installation.scheduled`; técnico inexistente o de otra organización → 400; cerrar sin equipos → 400 con la lista de faltantes; cerrar con checklist incompleto → 400; cierre correcto mueve a `installed`, proyecto `completed` y emite `installation.closed`; equipos congelados tras el cierre (409); agenda del técnico solo trae lo suyo; materiales solo con `projects.update`.
- [ ] Commit `feat(field_ops): equipos, materiales, agenda y cierre de instalación`.

### Task 6: Inspección

**Files:**
- Create: `backend/app/modules/field_ops/inspections.py`
- Modify: `case_hooks.py`, `router.py`, `schemas.py`
- Test: `backend/tests/test_field_inspections.py`

**Interfaces:**
- Produces: `schedule_inspection`, `record_inspection_result`; guardas `guard_inspection_scheduled`, `guard_inspection_passed`, `guard_inspection_failed`; suscriptor `project.created`.

- [ ] Tests: agendar con el expediente en `installed` mueve a `inspection_pending`; segunda pendiente → 409; aprobada marca `inspection_approved` y habilita la guarda de cobro; fallida vuelve a `ready_to_install`, proyecto `scheduled`, intento conservado; resultado dos veces → 409; guarda de cobro bloquea sin inspección aprobada.
- [ ] Commit `feat(field_ops): inspección con intentos y reintento`.

### Task 7: Frontend

**Files:**
- Create: `frontend/src/features/field-ops/components/{ConditionsPanel,PermitsPanel,EquipmentPanel,MaterialsPanel,InspectionsPanel,CloseInstallationPanel}.tsx`, `frontend/src/features/field-ops/AgendaPage.tsx`, `frontend/src/features/field-ops/module5Api.ts`
- Modify: `ProjectDetailPage.tsx` (checklist por sección y "No aplica", paneles nuevos), `app/router.tsx` y `config/navigation.ts` (habilitar "Mi agenda" y "Permisos e inspecciones" si aplica), `types/`
- Verificación: `npm run build` limpio.

- [ ] Paneles con TanStack Query, errores del backend mostrados tal cual (vienen en español).
- [ ] Commit `feat(field_ops): pantallas del módulo 5`.

### Task 8: Documentación de entrega

- [ ] `docs/contratos-cadena-b.md` iniciado: rutas, eventos, guardas y cambios al paquete de José.
- [ ] `CLAUDE.md` solo si cambió algo que otra sesión deba saber.
- [ ] Resumen para la próxima actualización del artefacto (no se actualiza hasta el merge con `main`).
