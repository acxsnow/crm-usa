# Agenda «Pendientes» e «Historial» — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`.

**Goal:** Que la agenda abra con lo que falta por hacer (atrasadas primero, hoy y lo que sigue) y que lo cerrado viva en un historial paginado.

**Spec:** `docs/superpowers/specs/2026-10-16-agenda-pendientes-historial-design.md`

## Global Constraints

- Sin `view`, la API se comporta igual que hoy.
- El técnico solo ve lo suyo (filtro en el servidor).
- «Hoy» es el de la organización (`field_ops.clock.org_today`).
- Paquete de Mateo: avisarle. Commit solo cuando José lo pida; nada a main.

## Review Focus

- Una orden atrasada sin cerrar aparece aunque sea de hace semanas.
- Cerradas y canceladas nunca salen en Pendientes.
- La paginación es de la base, con el orden correcto en cada vista.

---

### Task 1: API

- [x] Pruebas que fallan en `tests/test_agenda_views.py` (pendientes, historial, técnico, `days_late`, total).
- [x] `installation.list_agenda`: parámetro `view` y consulta por vista; devuelve la consulta para paginar en la base.
- [x] Router: `view`, `date_from` opcional en pendientes, `paginate`, `days_late`; `AgendaRow.days_late`.
- [x] Ver pasar las nuevas y las de `test_field_installation.py`.

### Task 2: Pantalla

- [x] `module5Api.ts` y `types/fieldOps.ts`: `view`, `days_late`.
- [x] `AgendaPage.tsx`: pestañas, Atrasadas / Hoy / días, historial paginado.
- [x] `npm run build` y `check_hooks.py`.

### Task 3: Verificación

- [x] Batería completa de pytest.
- [x] Navegador como técnico y como Administración: pendientes sin las cerradas e historial de la más reciente a la más vieja. Atrasadas: cubiertas por las pruebas (no había ninguna en la base local).
- [x] Recorrido manual (3.2) actualizado. Informar a José; commit cuando lo pida.
