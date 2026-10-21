# Control de la bodega, presupuesto y diario de obra — Plan de implementación

> **Para agentes:** se ejecuta en la sesión, paso a paso (modo de superpowers:executing-plans). Pasos con casillas `- [ ]`. Una fase por entrega: no se abre la siguiente hasta que la anterior pase `pytest` y `npm run build`.

**Goal:** Delta HVAC sabe qué hay en la bodega, autoriza por sistema la salida de material, precarga la lista de cada tipo de trabajo, compara lo presupuestado con lo real y sigue día por día las obras de varios días.

**Spec:** `docs/superpowers/specs/2026-10-19-control-bodega-design.md`

## Global Constraints

- Paquete nuevo `app/modules/warehouse/`. Archivos compartidos (`shared/permissions.py`, `api/v1/router.py`, `navigation.ts`, `router.tsx`) reciben **solo líneas nuevas**.
- Todo lleva `organization_id` del token, nunca del cliente. Permiso por ruta. Auditoría en cada escritura.
- Dinero con `Decimal` (`billing/money.py`); cantidades con `Numeric(10,2)`.
- Numeración de documentos con `billing/numbering.py` (serie nueva `SAL`); nada de contar filas.
- Paginación en la base (`shared/pagination.py`) y `x-total-count`, como el resto de listados.
- Migraciones Alembic: la primera es `0027_warehouse.py`; las siguientes se renumeran encima de la del otro al integrar.
- Fechas: el «hoy» es el de la organización (`shared/datetime_utils.py`), no el del contenedor.
- Commit solo cuando José lo pida; nada directo a `main`.

## Review Focus

- Una salida autorizada y entregada baja el saldo una sola vez; entregarla dos veces no descuenta dos veces.
- Sin existencias se entrega con aviso y queda el motivo; nunca un bloqueo silencioso.
- El mismo material no se cuenta dos veces en el costo real (entrada a bodega ≠ costo de la obra).
- Aislamiento por organización en artículos, existencias, movimientos, órdenes, presupuestos y diario.
- El técnico no ve saldos ni costos; solo pide salida y llena su diario.

---

## Fase 0 — Carga inicial de bodega

### Task 0.1: Modelo y migración

- [x] `0027_warehouse.py`: `warehouse_items`, `warehouse_locations`, `warehouse_stock`, `warehouse_movements`.
- [x] Pruebas que fallan (`tests/test_warehouse_stock.py`): alta de artículo; movimiento de entrada sube el saldo; salida lo baja; el saldo no se toca dos veces por el mismo movimiento; aislamiento por organización.
- [x] `warehouse/catalogs.py` con categorías y unidades de la hoja «Listas».

### Task 0.2: Importación del Excel y conteo inicial

- [x] Endpoint `POST /warehouse/import` (permiso `warehouse.manage`): recibe el Excel del catálogo, crea artículos y un movimiento `entrada` por «conteo inicial». Informe de filas creadas y errores por fila.
- [x] `POST /warehouse/counts` (permiso `warehouse.count`): conteo por ubicación; las diferencias quedan como movimiento `ajuste` con motivo.
- [x] Pruebas: importar dos veces no duplica artículos (por SKU); fila inválida no aborta el resto; el ajuste cuadra el saldo.

### Task 0.3: Pantallas

- [x] `WarehouseItemsPage` (`/warehouse/items`) y `WarehouseStockPage` (`/warehouse`), con `FilterBar` propio + `usePaginatedQuery` + `PaginationControls`.
- [x] Botón «Importar catálogo» y aviso de artículos en o bajo el mínimo.
- [x] Grupo de menú «Bodega» en `navigation.ts` y rutas en `router.tsx` (solo líneas nuevas).
- [x] `npm run build` y `scripts/check_hooks.py`.

### Task 0.4: Verificación

- [x] `pytest -q` completo en verde (574 pruebas).
- [ ] Cargar el Excel real y confirmar en pantalla que las existencias coinciden con lo contado.
      *Pendiente del cliente: aún no ha enviado el archivo del catálogo (solo el cuestionario).*

---

## Fase 1 — Existencias y salidas autorizadas (punto 1)

### Task 1.1: Órdenes de salida

- [x] `warehouse_release_orders` y `warehouse_release_lines` en la migración `0028_...`.
- [x] Serie `SAL` en `billing/numbering.py` (una línea).
- [x] Pruebas que fallan (`tests/test_warehouse_releases.py`): armar borrador; mandar a autorizar; autorizar con permiso; rechazar con motivo; entregar descuenta saldo; entregar sin existencias avisa y registra el motivo; entregar dos veces no descuenta dos veces; el técnico no puede autorizar (403); otra organización no ve la orden. (8 pruebas en verde.)

### Task 1.2: API y bandeja

- [x] Rutas: `GET/POST /warehouse/releases`, `POST /warehouse/releases/{id}/submit|approve|reject|deliver`, `GET /warehouse/releases/pending` (paginada).
- [x] Al entregar, las líneas alimentan los materiales del proyecto (`project_materials`) con el artículo y la cantidad entregada.
- [x] Eventos `warehouse.release_pending`, `warehouse.release_delivered` y aviso de existencias bajas `warehouse.stock_low` en el catálogo de `notifications` (el aviso se emite desde `warehouse/service.py` al cruzar el mínimo).

### Task 1.3: Pantallas

- [x] `WarehouseReleasesPage` (`/warehouse/releases`) y la bandeja «Salidas por autorizar», al estilo de `ActaReviewQueuePage`.
- [x] `WarehouseMovementsPage` (`/warehouse/movements`).
- [x] En el proyecto, la sección de materiales muestra lo entregado por bodega y de qué orden salió.
- [x] `npm run build` y `check_hooks.py`.

### Task 1.4: Verificación

- [x] `pytest -q` completo en verde (582 pruebas).
- [ ] Navegador: pedir una salida, autorizarla, entregarla y ver bajar el saldo y aparecer el material en el acta.

---

## Fase 2 — Listas predefinidas por tipo de trabajo (punto 2)

### Task 2.1: Plantillas de materiales

- [ ] `warehouse_kit_templates` y `warehouse_kit_items` en la migración `0029_...`.
- [ ] Pruebas (`tests/test_warehouse_kits.py`): crear lista; aplicarla a una orden de salida copia las líneas (snapshot); editar la plantilla no cambia las órdenes ya creadas; cantidades y calibres se pueden ajustar en la copia; agregar extras libres; aislamiento por organización.

### Task 2.2: API y pantallas

- [ ] Rutas `GET/POST/PUT/DELETE /warehouse/kits` y `POST /warehouse/kits/{id}/apply` (permiso `warehouse.kits_manage`).
- [ ] `WarehouseKitsPage` (`/warehouse/kits`), al estilo de `ChecklistTemplatesPage`.
- [ ] En la orden de salida, botón «Aplicar lista» y campos por línea: cantidad, calibre (`spec_label`) y notas.
- [ ] Seed con las listas reales cuando el cliente envíe el listado.
- [ ] `npm run build` y `check_hooks.py`.

### Task 2.3: Verificación

- [ ] `pytest -q` en verde; navegador: aplicar «Aire — estándar», ajustar un calibre y agregar un extra.

---

## Fase 3 — Presupuesto y estimado contra real (punto 3)

### Task 3.1: Presupuesto del proyecto

- [ ] `project_budgets` y `project_budget_lines` en la migración `0030_...`.
- [ ] Pruebas (`tests/test_project_budgets.py`): crear y aprobar presupuesto; generar desde una lista predefinida; una sola aprobación vigente; aislamiento por organización.

### Task 3.2: Estimado contra real

- [ ] Costo real del proyecto = salidas de bodega valoradas a costo del catálogo + `expenses` + compras directas a la obra (`supplier_invoice_lines` sin paso por bodega). Sin doble conteo (D-BOD-2).
- [ ] Pruebas: un material que entra por factura y luego sale no se cuenta dos veces; un equipo comprado directo a la obra sí cuenta; gastos aprobados del proyecto suman.
- [ ] `GET /warehouse/projects/{id}/budget-vs-actual` con desviación por categoría y total, y `GET /warehouse/purchasing` (compras sugeridas = presupuestado por venir − existencia).
- [ ] `WarehousePurchasingPage` (`/warehouse/purchasing`) y sección «Presupuesto» en el proyecto con la comparación.

### Task 3.3: Verificación

- [ ] `pytest -q` y `test_finance.py` en verde (no se rompe lo que ya cuenta costos).
- [ ] Navegador: presupuestar un proyecto, entregar material, cerrar y ver la desviación.

---

## Fase 4 — Diario de obra (punto 4)

### Task 4.1: Jornadas

- [ ] `project_day_logs` y `project_day_log_materials` en la migración `0031_...`.
- [ ] Pruebas (`tests/test_project_day_logs.py`): registrar la jornada con su técnico, horas y avance; material usado descuenta de la camioneta; los gastos del día se leen de `expenses` por fecha; dos jornadas con técnicos distintos; aislamiento por organización.

### Task 4.2: API y pantallas

- [ ] Rutas `GET/POST/PUT /projects/{id}/day-logs` (permiso `daylogs.manage`).
- [ ] Sección «Diario» en `ProjectDetailPage`: una línea por día con técnico, qué se hizo, avance, qué faltó, qué llevar al día siguiente y gastos del día.
- [ ] La Agenda marca las obras de varios días (más de una jornada).
- [ ] `npm run build` y `check_hooks.py`.

### Task 4.3: Verificación

- [ ] `pytest -q` en verde.
- [ ] Navegador: registrar tres jornadas de un mismo proyecto con dos técnicos y ver el diario y los gastos por día.

---

## Verificación transversal (al cerrar cada fase)

- [ ] `pytest -q` completo en verde y `npm run build`.
- [ ] Permisos por ruta y aislamiento por organización (probar con un usuario de otra organización).
- [ ] `docs/qa/recorrido-manual.md` actualizado con el recorrido de la fase.
- [ ] Informar a José lo entregado; commit cuando lo pida.
