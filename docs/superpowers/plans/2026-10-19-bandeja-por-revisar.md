# Bandeja «Por revisar» — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Una sola bandeja de Administración con Documentos, Actas por confirmar, Inspección municipal y Cobros por crear.

**Spec:** `docs/superpowers/specs/2026-10-19-bandeja-por-revisar-design.md`

## Global Constraints

- Cada pestaña con su permiso; aislamiento por organización.
- «Cobros por crear» reusa `_to_create`, sin una segunda versión de la regla.
- Paquetes de Mateo: avisarle. Commit solo cuando José lo pida; nada a main.

## Review Focus

- Una inspección aprobada saca el proyecto de la cola; una fallida lo deja como «reagendar».
- Las rutas viejas siguen funcionando (redirigen).

---

### Task 1: API

- [x] Pruebas que fallan (`tests/test_review_inbox.py`): cola de inspección (sin agendar, agendada, fallida, aprobada fuera, sin cerrar fuera, orden, técnico 403, otra organización vacía); `to-create` (acta confirmada sin cobro aparece, sin permiso 403).
- [x] `inspection_queue_stmt` y su ruta; `claims_to_create` y su ruta.
- [x] Ver pasar las nuevas y las de inspecciones, facturación y paginación.

### Task 2: Pantalla

- [x] `ReviewInboxPage` (`/review?tab=`), con las pestañas por permiso; las colas de documentos y actas como componentes.
- [x] Pestañas nuevas: inspección y cobros.
- [x] Menú «Por revisar»; redirigir `/documents` y `/acta-reviews`.
- [x] `npm run build` y `check_hooks.py`.

### Task 3: Verificación

- [x] Batería completa de pytest: 565 pasan.
- [x] Navegador como Administración (las cuatro pestañas y sus enlaces) y como Contabilidad (solo Cobros).
- [ ] Recorrido manual actualizado (hecho). Informar a José; commit cuando lo pida.
