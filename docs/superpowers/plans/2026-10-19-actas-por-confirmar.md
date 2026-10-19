# «Actas por confirmar» y aviso al cerrar — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Administración se entera de cada instalación cerrada (aviso) y tiene una bandeja con las actas por confirmar. Sale el formulario «Crear proyecto».

**Spec:** `docs/superpowers/specs/2026-10-19-actas-por-confirmar-design.md`

## Global Constraints

- Permiso `checklists.approve` para la bandeja y como audiencia del aviso.
- Paginación en la base.
- Paquetes de Mateo (`field_ops`, `notifications`): avisarle. Commit solo cuando José lo pida; nada a main.

## Review Focus

- Un acta confirmada sale de la bandeja; una devuelta y vuelta a cerrar entra de nuevo.
- El técnico no ve la bandeja (403).
- Aislamiento por organización.

---

### Task 1: API

- [x] Pruebas que fallan (`tests/test_acta_review_queue.py`): cerrada sin confirmar aparece; confirmada no; orden por fecha de cierre; días esperando; otra organización no; técnico 403. Aviso: `installation.closed` llega a quien tiene `checklists.approve` con el enlace al paso 7, no al técnico.
- [x] Catálogo, `_resolve`, `dispatch.EVENTS`; consulta y ruta de la bandeja.
- [x] Ver pasar las nuevas, `test_notifications.py` y `test_field_reviews.py`.

### Task 2: Pantalla

- [x] `ActaReviewQueuePage` y ruta `/acta-reviews`, menú con permiso.
- [x] `?paso=` abre el paso y baja hasta él.
- [x] Quitar el formulario «Crear proyecto».
- [x] `npm run build` y `check_hooks.py`.

### Task 3: Verificación

- [x] Batería completa de pytest: 562 pasan.
- [x] Navegador: Administración ve la fila de CASE-2026-0100, abre en el paso 7 con «Confirmar» a la vista; el técnico no entra a la bandeja; sin «Crear proyecto». El aviso y «confirmar → sale» quedan cubiertos por las pruebas (no confirmé el acta de José).
- [ ] Recorrido manual actualizado (hecho). Informar a José; commit cuando lo pida.
