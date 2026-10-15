# Contador de días en «Pendiente de aprobación» — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que Administración y el vendedor vean cuántos días hábiles lleva un expediente esperando aprobación (gris, rojo al pasar el límite) en el tablero, la cola de documentos y la revisión, y que Administración pueda correr las alertas en el momento.

**Architecture:** Un módulo nuevo `cases/approval_clock.py` calcula `approval_wait` con la misma regla de la alerta del módulo 7 (`business_days_between`, zona y «hoy» de la organización, umbral de `notification_settings`). Tres respuestas existentes lo suman como campo nuevo. Una ruta nueva `POST /notifications/alerts/run` llama a `daily_alerts()`. Un componente `ApprovalDays.tsx` lo pinta en tres pantallas.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pytest + SQLite en memoria; React 18 + TypeScript + TanStack Query.

**Spec:** `docs/superpowers/specs/2026-10-14-contador-dias-aprobacion-design.md`

## Global Constraints

- La regla de días es una sola: `notifications.service.business_days_between` sobre `field_ops.clock.local_date(submitted_at, zona)` y `org_today()`. No se duplica la lógica en el frontend ni en otro módulo.
- `approval_wait` no escribe nada: leer el umbral **sin** crear la fila de ajustes (si no existe, umbral 3, el valor por defecto del módulo 7). `get_settings_row()` crea la fila y no se usa desde un GET.
- Imports al inicio del archivo: no hay ciclo (`notifications.service` y `field_ops.clock` no importan `cases` al cargar).
- Paquete de Mateo: solo una ruta nueva en `notifications/router.py` y el botón en `NotificationsPage.tsx`; nada existente cambia. Avisarle antes de integrar.
- Respuestas: campos nuevos, ningún campo existente cambia de nombre ni de forma.
- Mensajes en español; toda consulta por `organization_id` del token.
- Sin commits hasta que José lo pida. Verificación: `docker compose exec api python -m pytest -q`; `docker compose exec frontend npm run build`; `scripts/check_hooks.py`.

## Review Focus

- Un fin de semana entre el envío y hoy no suma días.
- La devolución no cambia los días; `on_hold` y las demás etapas dan `null`.
- El tablero con 20 tarjetas no hace una consulta por tarjeta.
- «Revisar ahora» dos veces el mismo día no duplica avisos; sin `notifications.manage` → 403; otra organización no se toca.
- El vendedor ve `approval_wait` de sus propios expedientes sin permiso de ajustes.

---

### Task 1: `approval_clock.py` con sus pruebas

**Files:** crear `backend/app/modules/cases/approval_clock.py`, crear `backend/tests/test_approval_clock.py`.

- [x] Prueba que falla: con la zona de la organización y un «hoy» fijo (monkeypatch de `org_today`), un expediente en `pending_approval` enviado hace 0, 2 y 4 días hábiles con umbral 3 da `business_days` 0/2/4 y `overdue` falso/falso/verdadero y `limit` 3; enviado un viernes y «hoy» lunes da 1; en `on_hold`, `approved` o sin `submitted_at` da `None`; sin fila de ajustes el umbral es 3 y no se crea la fila.
- [x] Correr y ver que falla (módulo no existe).
- [x] Implementar `wait_context(db, organization_id)` (zona, hoy, umbral leído con `select`, sin crear) y `approval_wait(case, ctx)`.
- [x] Correr y ver que pasa.

### Task 2: `approval_wait` en tablero, cola y formulario

**Files:** `backend/app/modules/cases/intake.py` (`board`, respuesta del formulario), `backend/app/modules/cases/documents.py` (`review_queue`), pruebas en `backend/tests/test_approval_clock.py`.

- [x] Prueba que falla: `GET /case-board` trae `approval_wait` en la tarjeta de un expediente pendiente (días y `overdue` correctos) y `null` en uno aprobado; `GET /documents/review-queue` lo trae en cada fila; `GET /cases/{id}/form` lo trae al nivel superior; el vendedor dueño lo recibe; devolver el expediente (`substatus` `returned`) no cambia los días.
- [x] Correr y ver que falla.
- [x] Implementar: un `wait_context` por respuesta y `approval_wait` por tarjeta o fila.
- [x] Correr y ver que pasa; correr `tests/test_cases_intake.py`, `tests/test_pagination_everywhere.py` y las pruebas del tablero para ver que nada se rompió.

### Task 3: «Revisar ahora»

**Files:** `backend/app/modules/notifications/router.py` (ruta nueva), pruebas en `backend/tests/test_approval_clock.py`.

- [x] Prueba que falla: `POST /notifications/alerts/run` con Administración crea el aviso `case.approval_overdue` de un expediente demorado y devuelve `{"created": N}`; la segunda llamada devuelve `0`; el vendedor recibe 403; un expediente de otra organización no genera aviso.
- [x] Correr y ver que falla.
- [x] Implementar la ruta con `require_permission("notifications.manage")`, `organization_id` del token y `service.daily_alerts()`.
- [x] Correr y ver que pasa; correr `tests/test_notifications*.py`.

### Task 4: Frontend

**Files:** crear `frontend/src/features/sales/ApprovalDays.tsx`; `features/sales/api.ts` (tipos), `CasesBoardPage.tsx`, `DocumentsQueuePage.tsx`, `CaseReviewPage.tsx`, `features/notifications/api.ts` y `NotificationsPage.tsx`; estilos en `sales.css`.

- [x] Tipo `ApprovalWait` y campo opcional en la tarjeta del tablero, `QueueRow` y la respuesta del formulario.
- [x] `ApprovalDays`: «Enviado hoy» con 0; «1 día hábil»; «N días hábiles»; con `overdue`, rojo y «· límite L». No pinta nada con `null`.
- [x] Usarlo en la tarjeta de «Pendiente de aprobación», en la fila de la cola (junto a «enviado …») y en el encabezado de la revisión (bajo «Enviado»).
- [x] Pestaña Alertas: botón **Revisar ahora** que llama `POST /notifications/alerts/run`, muestra «Se crearon N avisos» o «No había nada nuevo para avisar», y refresca la campana.
- [x] `npm run build` y `check_hooks.py` en verde.

### Task 5: Verificación

- [x] Batería completa de pytest.
- [x] Navegador (Playwright): como Administración, tablero con una tarjeta gris y una roja; cola con el chip; revisión con el chip bajo «Enviado»; Alertas → umbral 1 → **Revisar ahora** → mensaje y aviso en la campana; segunda vez → «No había nada nuevo». Como vendedor: ve el chip en su expediente.
- [x] Actualizar `docs/qa/recorrido-manual.md` (paso 2.1: qué contador ver y el botón) y el resumen para el artefacto (cierra G7 visible; no hay ID de hallazgo).
- [ ] Informar a José con lo que pasó y lo que no; no comitear hasta que lo pida.
