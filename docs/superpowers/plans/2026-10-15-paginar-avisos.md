# Paginar «Mis avisos» — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que «Mis avisos» se pueda recorrer completo por páginas y que la guardia de paginación no deje pasar otro listado con forma de objeto.

**Spec:** `docs/superpowers/specs/2026-10-15-paginar-avisos-design.md`

## Global Constraints

- Paginación común (`app/shared/pagination.py`); nada propio.
- La campana no cambia de comportamiento visible (8 más recientes y contador).
- Paquete de Mateo: solo lo necesario; avisarle.
- José pidió comitear al terminar.

## Review Focus

- Avisos de otra persona nunca aparecen.
- «Solo sin leer» + página 2 no repite ni salta avisos.
- La guardia detecta objetos con `items` sin paginar.

---

### Task 1: Guardia

- [x] `tests/test_pagination_everywhere.py`: incluir GET cuya respuesta tiene `items` (modelo o `dict`).
- [x] Correr y ver que falla señalando `/api/v1/notifications` (y candidatos de conciliación).
- [x] Candidatos de conciliación a `EXCEPTIONS` con su motivo.

### Task 2: API

- [x] Prueba que falla en `tests/test_notifications.py`: páginas con `offset`, `X-Total-Count`, orden, `unread`, solo los propios.
- [x] `GET /notifications` con `pagination_params` y `paginate()`; ver pasar la prueba y la guardia.
- [x] Correr las pruebas de notificaciones.

### Task 3: Frontend

- [x] `notifications/api.ts`: `listNotices` con `fetchPage`.
- [x] `NotificationsPage.tsx` (Mis avisos): `usePaginatedQuery` de a 30 y `PaginationControls`.
- [x] `NotificationBell.tsx`: página 1 de 8.
- [x] `npm run build` y `check_hooks.py`.

### Task 4: Verificación y entrega

- [x] Batería completa de pytest.
- [x] Navegador: botones de página, filtro sin leer, marcar todas, campana.
- [x] Commit del arreglo de PDF y de este cambio (pedido por José) y subir.
