# Costo del trabajo (fases 1 y 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cada trabajo (rebate y particular) tenga un estimado armado desde plantillas de costo y, al final, un panel «Costo del trabajo» con estimado contra real, sin volver a capturar lo que el sistema ya registra.

**Architecture:** El presupuesto de proyecto que ya existe (`app/modules/warehouse/budgets.py`) pasa a ser el estimado, con precio esperado. Se agregan plantillas de costo, costos reales manuales (mano de obra, representante) y cobros adicionales en efectivo, en un módulo nuevo `app/modules/warehouse/jobcost.py` con su router `jobcost_router.py`. Una sola función, `job_costing()`, arma ingreso, costo real por concepto y estimado; la usan el panel y el reporte de rentabilidad.

**Tech Stack:** FastAPI + SQLAlchemy 2 async + Alembic (backend), React 18 + TypeScript + React Query (frontend). Dinero siempre `Decimal` con `billing/money.py`.

**Spec:** `docs/superpowers/specs/2026-10-22-costo-del-trabajo-design.md`

## Global Constraints

- Dinero en `Decimal` con `to_money`/`money_sum`; nunca `float` (la capa de dinero rechaza floats).
- Aislamiento por organización con el `organization_id` del token en toda consulta; un registro ajeno responde 404.
- Toda lista nueva paginada con `pagination_params` + `paginate` (lo exige `tests/test_pagination_everywhere.py`).
- D-BOD-2: nada se cuenta dos veces; lo que entra a bodega cuesta cuando sale.
- Mano de obra, pago del representante y costos nunca visibles al técnico ni en factura/cotización del cliente.
- Sin permisos nuevos: ver = `budgets.manage` | `budgets.approve` | `warehouse.read`; editar = `budgets.manage`; aprobar = `budgets.approve`. Cobro adicional del técnico: `daylogs.manage` sobre un proyecto que ve (`field_ops.access.get_visible_project`).
- Archivos compartidos (`api/v1/router.py`, `navigation.ts`, `router.tsx`, `permissions.py`): solo líneas nuevas.
- Migración nueva `0033`, `down_revision = "0032"`, con `downgrade`.
- Textos de la interfaz en español; categorías nuevas: `sales_rep` = «Representante», `consumables` = «Consumibles».
- Plantillas iniciales exactas (spec §4.2): «Trabajo particular ideal» (ganancia objetivo 40%, permisos 10%, materiales 30%, mano de obra 20%); «Pedestal (rebate) con personal propio» (representante 800, permisos 238, materiales 1.062, mano de obra 600; precio 4.200); «Pedestal (rebate) con subcontratista» (representante 800, permisos 230, materiales 1.070, contratista 1.050; precio 4.200).

## Review Focus

1. Trabajo sin ingreso todavía (sin factura ni cobro): el panel muestra las cifras del estimado con la etiqueta «estimado» y margen sin dividir entre cero → prueba en Task 5.
2. Plantilla por porcentaje aplicada sin precio esperado (rebate sin tarifa vigente, particular sin precio): error claro 400 `expected_revenue_required`, no renglones en cero → prueba en Task 2.
3. Presupuesto aprobado (no editable) al que se intenta aplicar plantilla o cambiar el precio: 400 como hoy con `budget_not_editable` → prueba en Task 2.
4. Técnico que anota un cobro adicional en una obra que no es suya, o que intenta leer costos del panel: 404 / 403 → prueba en Task 4.
5. Factura de proveedor del subcontratista asignada al proyecto **y** línea manual de contratista por el mismo monto: se suman las dos (no se bloquea) pero el panel marca `possible_duplicate` → prueba en Task 5.

---

### Task 1: Modelo de datos y migración 0033

**Files:**
- Modify: `backend/app/modules/warehouse/catalogs.py` (BudgetCategory, BUDGET_CATEGORIES; nuevos JOB_CONCEPTS, CONCEPT_OF_CATEGORY, TEMPLATE_MODES, EXTRA_CHARGE_METHODS)
- Modify: `backend/app/modules/warehouse/models.py` (columnas en ProjectBudget; modelos nuevos)
- Create: `backend/alembic/versions/0033_job_costing.py`
- Test: `backend/tests/test_job_costing.py`

**Interfaces:**
- Produces:
  - `BudgetCategory.SALES_REP = "sales_rep"`, `BudgetCategory.CONSUMABLES = "consumables"`; `"target_profit"` es una categoría **solo de plantilla** (`TEMPLATE_ONLY_CATEGORIES = {"target_profit"}`), nunca en presupuesto.
  - `JOB_CONCEPTS: dict[str, str]` en orden: `sales_rep` «Representante», `permits` «Permisos», `materials` «Materiales», `labor` «Mano de obra», `other` «Otros».
  - `CONCEPT_OF_CATEGORY: dict[str, str]`: sales_rep→sales_rep; permit→permits; materials, equipment, consumables→materials; labor, contractor→labor; services, other, field_expenses→other.
  - `ProjectBudget.expected_revenue: Decimal | None` (MONEY, nullable), `ProjectBudget.template_id: UUID | None` (FK cost_templates, nullable).
  - `CostTemplate` (`cost_templates`): organization_id, name (String 120, único por org), job_type (String 100, nullable), applies_to (String 20: `rebate` | `particular` | `both`, default `both`), active (bool), lines (relationship lazy="raise").
  - `CostTemplateLine` (`cost_template_lines`): template_id (FK cascade), category (String 30), description (String 255), mode (`percent` | `amount`), value (MONEY), sort_order.
  - `ProjectCostEntry` (`project_cost_entries`): project_id, entry_date (Date), category (String 30), description (String 255), amount (MONEY), person_user_id (FK users, nullable), person_name (String 255, nullable), notes, created_by_user_id.
  - `ProjectExtraCharge` (`project_extra_charges`): project_id, charge_date, description, amount, payment_method (String 20, default `cash`), received_by_user_id (quien lo cobró en la obra), delivered_at (DateTime, nullable = «por entregar»), delivered_to_user_id (nullable), created_by_user_id.

- [ ] **Step 1: Write the failing test**

```python
async def test_las_categorias_nuevas_y_los_conceptos_cubren_todo():
    from app.modules.warehouse.catalogs import BUDGET_CATEGORIES, CONCEPT_OF_CATEGORY, JOB_CONCEPTS
    from app.modules.warehouse.costing import ACTUAL_LABELS
    assert BUDGET_CATEGORIES["sales_rep"] == "Representante"
    assert BUDGET_CATEGORIES["consumables"] == "Consumibles"
    assert list(JOB_CONCEPTS) == ["sales_rep", "permits", "materials", "labor", "other"]
    # Toda categoría que puede tener costo real cae en un concepto del tablero.
    assert set(ACTUAL_LABELS) <= set(CONCEPT_OF_CATEGORY)
    assert set(CONCEPT_OF_CATEGORY.values()) <= set(JOB_CONCEPTS)
```

- [ ] **Step 2: Run it to verify it fails**
Run: `cd backend && .venv/bin/python -m pytest -q tests/test_job_costing.py` → FAIL (ImportError `JOB_CONCEPTS`).

- [ ] **Step 3: Add the categories, constants and models; write migration `0033_job_costing.py`** (create the four tables and the two columns with indexes `organization_id, project_id` like 0030/0031; `downgrade` drops them). Import nothing new in `alembic/env.py` (models already load via `app/db/all_models.py`).

- [ ] **Step 4: Run tests**
Run: `.venv/bin/python -m pytest -q tests/test_job_costing.py tests/test_project_budgets.py tests/test_project_costing.py` → PASS.

- [ ] **Step 5: Migration both ways against Postgres**
Run: `docker compose exec api alembic upgrade head && docker compose exec api alembic downgrade 0032 && docker compose exec api alembic upgrade head` → sin errores.

- [ ] **Step 6: Commit** `feat(costo): modelo de plantillas, costos reales y cobros adicionales (migración 0033)`

---

### Task 2: Plantillas de costo y estimado con precio esperado

**Files:**
- Create: `backend/app/modules/warehouse/jobcost.py` (servicio)
- Create: `backend/app/modules/warehouse/jobcost_router.py`
- Modify: `backend/app/api/v1/router.py` (una línea `include_router`)
- Modify: `backend/app/modules/warehouse/budgets.py` (`save_budget` acepta `expected_revenue`; `budget_out` lo devuelve con `expected_profit` y `template_id`)
- Modify: `backend/app/modules/warehouse/router.py` (`BudgetIn.expected_revenue: str | None = None`)
- Test: `backend/tests/test_job_costing.py`

**Interfaces:**
- Consumes: modelos de Task 1; `budgets.get_budget`, `budgets._editable`, `budgets.save_budget`; `billing.program_config.rate_for(db, *, organization_id, program_id, on) -> ProgramRebateRate | None`.
- Produces:
  - `async def ensure_default_templates(db, organization_id) -> None` — crea las 3 plantillas de Global Constraints si la organización no tiene ninguna (se llama al listar).
  - `async def save_template(db, *, organization_id, user, data: dict, template_id=None) -> CostTemplate`; `async def delete_template(...)`; `def template_out(t, lines) -> dict`.
  - `async def default_expected_revenue(db, organization_id, project) -> Decimal | None` — rebate (proyecto con caso y programa): `rate_for(..., on=org_today)` del programa; particular: total de la cotización aceptada del proyecto si existe, si no `None`.
  - `async def apply_template(db, *, organization_id, user, budget_id, template_id, expected_revenue: Decimal | None) -> ProjectBudget` — reemplaza los renglones **no ligados a artículo** del borrador por los de la plantilla (los de material del catálogo, que vienen de una lista, se conservan); `percent` → `to_money(precio * valor / 100)`; `amount` → valor; guarda `template_id` y `expected_revenue` (si no viene, usa `default_expected_revenue`).
  - `def estimate_summary(budget, renglones, template_lines) -> dict` con `expected_revenue`, `total_cost`, `expected_profit`, `expected_margin_pct` (float, 1 decimal, None sin precio), `target_profit_pct` (de la plantilla, None si no tiene), `below_target: bool`.
  - Rutas: `GET/POST /warehouse/cost-templates`, `PUT/DELETE /warehouse/cost-templates/{id}` (`budgets.manage` para escribir; leer con los permisos de ver), `POST /warehouse/budgets/{budget_id}/apply-template` body `{template_id, expected_revenue?}`.

- [ ] **Step 1: Write the failing tests**

```python
async def test_la_organizacion_arranca_con_las_tres_plantillas(app_client, login, active_admin_user):
    h = await login(active_admin_user.email)
    nombres = {t["name"] for t in (await app_client.get(f"{API}/warehouse/cost-templates", headers=h)).json()}
    assert nombres == {"Trabajo particular ideal", "Pedestal (rebate) con personal propio",
                       "Pedestal (rebate) con subcontratista"}

async def test_plantilla_por_porcentaje_reparte_el_precio(app_client, login, db, seeded_org, active_admin_user):
    # «Trabajo particular ideal» sobre 10.000: permisos 1.000, materiales 3.000, mano de obra 2.000,
    # ganancia esperada 4.000 = 40%, no queda por debajo del objetivo.
    ...
    assert (r["by_category"]["permit"], r["by_category"]["materials"], r["by_category"]["labor"]) == (
        "1000.00", "3000.00", "2000.00")
    assert (r["expected_profit"], r["expected_margin_pct"], r["below_target"]) == ("4000.00", 40.0, False)

async def test_pedestal_con_personal_propio_deja_1500(...):
    # precio 4.200 y montos fijos de la plantilla → ganancia esperada 1.500 (35,7%).
    assert (r["expected_profit"], r["expected_margin_pct"]) == ("1500.00", 35.7)

async def test_rebate_toma_el_precio_de_la_tarifa_del_programa(...):
    # proyecto de un caso con programa y tarifa vigente 4.200 → apply-template sin precio usa 4200.00

async def test_plantilla_por_porcentaje_sin_precio_da_400(...):
    assert (r.status_code, r.json()["code"]) == (400, "expected_revenue_required")

async def test_no_se_aplica_plantilla_a_un_presupuesto_aprobado(...):
    assert (r.status_code, r.json()["code"]) == (400, "budget_not_editable")

async def test_aplicar_plantilla_conserva_el_material_de_la_lista(...):
    # presupuesto con un renglón de artículo (de apply-kit) + plantilla por monto → el renglón del artículo sigue.

async def test_el_tecnico_no_ve_plantillas(...):
    assert (await app_client.get(f"{API}/warehouse/cost-templates", headers=tecnico)).status_code == 403
```

- [ ] **Step 2: Run** `pytest -q tests/test_job_costing.py` → FAIL (404 en las rutas).
- [ ] **Step 3: Implement the service and router above**, siguiendo el estilo de `kits.py` (validación de renglones, auditoría `cost_template.saved`, `budget.template_applied`).
- [ ] **Step 4: Run** `pytest -q tests/test_job_costing.py tests/test_project_budgets.py tests/test_pagination_everywhere.py` → PASS.
- [ ] **Step 5: Commit** `feat(costo): plantillas de costo y estimado con precio esperado`

---

### Task 3: Costos reales manuales (mano de obra, representante)

**Files:**
- Modify: `backend/app/modules/warehouse/jobcost.py`, `jobcost_router.py`
- Modify: `backend/app/modules/warehouse/costing.py` (`project_actual_costs` suma `project_cost_entries`)
- Test: `backend/tests/test_job_costing.py`

**Interfaces:**
- Produces:
  - `async def save_cost_entry(db, *, organization_id, user, project_id, data: dict, entry_id=None) -> ProjectCostEntry` — categorías permitidas: `labor`, `contractor`, `sales_rep`, `permit`, `consumables`, `other`; monto > 0; `person_user_id` debe ser usuario activo de la organización si viene.
  - `async def delete_cost_entry(...)`; `cost_entries_stmt(organization_id, project_id)`; `cost_entry_out(e, person_name) -> dict`.
  - Rutas (`budgets.manage`): `GET/POST /warehouse/projects/{project_id}/cost-entries` (GET paginado), `PUT/DELETE /warehouse/projects/{project_id}/cost-entries/{entry_id}`.
  - `project_actual_costs(...)` ahora incluye por categoría la suma de las entradas del proyecto.

- [ ] **Step 1: Write the failing tests**

```python
async def test_la_mano_de_obra_anotada_suma_al_costo_real(...):
    # entrada labor 600 a nombre del técnico → budget-vs-actual fila labor actual "600.00"

async def test_el_pago_de_luis_puede_ir_como_representante_o_como_mano_de_obra(...):
    # sales_rep 800 → fila sales_rep 800; otra obra con labor 800 «Luis» → fila labor 800

async def test_monto_cero_o_categoria_inventada_da_400(...)
async def test_el_tecnico_no_puede_anotar_ni_ver_costos(...):  # 403 en GET y POST
async def test_otra_organizacion_no_ve_las_entradas(...):  # 404
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** `pytest -q tests/test_job_costing.py tests/test_project_costing.py` → PASS.
- [ ] **Step 5: Commit** `feat(costo): mano de obra y representante como costo real del trabajo`

---

### Task 4: Cobros adicionales en efectivo

**Files:**
- Modify: `backend/app/modules/warehouse/jobcost.py`, `jobcost_router.py`
- Test: `backend/tests/test_job_costing.py`

**Interfaces:**
- Produces:
  - `async def create_extra_charge(db, *, organization_id, user, project_id, data: dict) -> ProjectExtraCharge` — `received_by_user_id = user.id` si quien anota es técnico; Oficina puede elegir quién lo recibió.
  - `async def mark_delivered(db, *, organization_id, user, charge_id) -> ProjectExtraCharge` — solo `budgets.manage`; idempotente (marcar dos veces no cambia la fecha); auditoría `extra_charge.delivered`.
  - `extra_charges_stmt(organization_id, project_id, *, own_user_id=None)`; `extra_charge_out(c) -> dict` con `status`: `por_entregar` | `recibido`.
  - Rutas: `GET/POST /warehouse/projects/{project_id}/extra-charges` (técnico con `daylogs.manage`: solo proyecto visible y solo los suyos en el GET; Oficina con los permisos de ver: todos), `POST /warehouse/extra-charges/{id}/deliver` (`budgets.manage`), `GET /warehouse/extra-charges/pending` (paginado, `budgets.manage`: todo lo por entregar de la organización).

- [ ] **Step 1: Write the failing tests**

```python
async def test_el_tecnico_anota_el_extra_y_queda_por_entregar(...):
    # técnico de la obra: POST {description: "Breaker 30A y 10 ft de cable", amount: "150"} → 201,
    # status "por_entregar", payment_method "cash", received_by = técnico

async def test_aldo_marca_recibido_y_deja_de_estar_pendiente(...):
    # deliver → status "recibido"; /extra-charges/pending ya no lo trae; deliver otra vez → mismo delivered_at

async def test_el_tecnico_no_anota_extras_en_obra_ajena(...):  # 404 project_not_found
async def test_el_tecnico_solo_ve_sus_extras(...)
async def test_el_tecnico_no_puede_marcar_recibido(...):  # 403
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat(costo): cobros adicionales en efectivo, del técnico a Aldo`

---

### Task 5: `job_costing()` — el resumen del trabajo, y rentabilidad con la misma suma

**Files:**
- Modify: `backend/app/modules/warehouse/costing.py`
- Modify: `backend/app/modules/finance/profitability.py` (`report` usa `project_actual_costs` y suma cobros adicionales al ingreso)
- Modify: `backend/app/modules/warehouse/jobcost_router.py` (`GET /warehouse/projects/{project_id}/job-costing`, permisos de ver)
- Test: `backend/tests/test_job_costing.py`, ajustar `tests/test_finance.py` si cambia una cifra esperada (explicar en el commit)

**Interfaces:**
- Consumes: `project_actual_costs`, `current_budget`, `estimate_summary` (Task 2), modelos de Task 1.
- Produces: `async def job_costing(db, *, organization_id, project_id) -> dict` con:
  - `kind`: `rebate` | `particular`.
  - `revenue`: `{"invoiced", "program", "extras", "collected", "total", "is_estimate": bool}` — `program`/`invoiced` = facturas del proyecto sin anular (rebate: cobros al programa; particular: facturas al cliente); `extras` = cobros adicionales (entregados o no); `total = invoiced + extras`; si `total == 0` se usa `expected_revenue` del estimado y `is_estimate = True`.
  - `costs`: `{"total", "by_concept": {concepto: {"estimated", "actual", "deviation", "sources": [...]}}, "by_category": {...}}` (conceptos de `JOB_CONCEPTS`, todos presentes aunque en cero).
  - `profit`: `{"actual", "estimated", "margin_pct", "estimated_margin_pct", "target_pct", "below_target"}` — `margin_pct` None si el ingreso es 0.
  - `extras_pending`: lista de cobros adicionales `por_entregar`.
  - `warnings`: lista de códigos; `possible_duplicate` cuando una línea manual `contractor`/`permit` tiene el mismo monto (±1,00) que una línea de factura de proveedor del proyecto en esa categoría.
- `profitability.report` y `job_costing` dan el mismo costo total para el mismo proyecto, y cada fila del reporte gana `estimated_margin_pct` (del estimado aprobado; None si no hay) para ver qué trabajos quedaron por debajo (spec §6).

- [ ] **Step 1: Write the failing tests**

```python
async def test_el_pedestal_cierra_con_su_ganancia_real(...):
    # Estimado «Pedestal con personal propio» (4.200). Real: cobro al programa 4.200 facturado,
    # salida de bodega por 1.180 de material, mano de obra 600, representante 800, permiso 238 (factura de proveedor).
    # → revenue.total 4200.00, costs.total 2818.00, profit.actual 1382.00, margin_pct 32.9,
    #   by_concept["materials"]["deviation"] == "118.00", below_target False (sin objetivo en esa plantilla)

async def test_sin_factura_el_panel_muestra_el_estimado(...):
    # solo estimado: revenue.is_estimate True, revenue.total == expected_revenue, margin_pct == estimated_margin_pct

async def test_sin_estimado_ni_ingreso_no_divide_entre_cero(...):
    # proyecto vacío → 200, margin_pct None, todos los conceptos "0.00"

async def test_el_extra_en_efectivo_suma_al_ingreso(...):
    # 4.200 programa + 150 extra → revenue.total 4350.00, revenue.extras "150.00"

async def test_subcontratista_por_factura_y_a_mano_avisa_posible_duplicado(...):
    # factura de proveedor contractor 1.050 al proyecto + entrada manual contractor 1.050
    # → costs.by_concept["labor"]["actual"] == "2100.00" y "possible_duplicate" in warnings

async def test_rentabilidad_y_panel_dan_el_mismo_costo(...):
    # mismo proyecto: report()["rows"][0]["costs"] == job_costing()["costs"]["total"]
    # y report()["rows"][0]["estimated_margin_pct"] == job_costing()["profit"]["estimated_margin_pct"]

async def test_el_tecnico_no_ve_el_costo_del_trabajo(...):  # 403
```

- [ ] **Step 2: Run** → FAIL. **Step 3: Implement** (`profitability.report`: cambiar `project_costs` por `project_actual_costs` de `warehouse.costing` —import local para evitar ciclo— y sumar extras al cobrado/esperado). **Step 4: Run** `pytest -q` completo → PASS (corregir y justificar cifras de `test_finance.py` que ahora incluyan bodega).
- [ ] **Step 5: Commit** `feat(costo): resumen del trabajo con ingreso, costo real por concepto y margen`

---

### Task 6: Panel «Costo del trabajo», plantillas y cobro adicional en el frontend

**Files:**
- Modify: `frontend/src/features/warehouse/api.ts` (tipos y llamadas de las rutas de Tasks 2–5)
- Create: `frontend/src/features/warehouse/JobCostPanel.tsx` (reemplaza a `ProjectBudgetPanel` en la ficha; reutiliza su editor de renglones)
- Create: `frontend/src/features/warehouse/JobCostCharts.tsx` (dona y barra en SVG propio, sin librería nueva)
- Create: `frontend/src/features/warehouse/CostTemplatesPage.tsx` (ruta `/warehouse/cost-templates`)
- Create: `frontend/src/features/warehouse/ExtraChargeForm.tsx` (técnico, en la ficha del proyecto)
- Modify: `frontend/src/features/field-ops/ProjectDetailPage.tsx` (usar `JobCostPanel`; mostrar `ExtraChargeForm` a quien tiene `daylogs.manage`)
- Modify: `frontend/src/config/navigation.ts`, `frontend/src/app/router.tsx` (una entrada «Plantillas de costo», permisos `budgets.manage`)

**Interfaces:**
- Consumes: `GET /warehouse/projects/{id}/job-costing` y las demás rutas.
- Produces: el panel del boceto aprobado — 4 cifras (margen real con el estimado al lado, ingreso, costos, ganancia; etiqueta «estimado» cuando `revenue.is_estimate`), dona ingreso, barra por concepto, tabla estimado/%/real/diferencia/fuente (rojo si real > estimado o ganancia < estimado), aviso `below_target`, lista «Efectivo por entregar» con botón «Recibido», acciones «Armar estimado», «Aplicar lista», «Anotar mano de obra / representante», «Anotar cobro adicional», «Aprobar estimado». Usable a 375 px de ancho.

- [ ] **Step 1: Implement** api + componentes. Formateo de dinero con el helper que ya usa `ProjectBudgetPanel`.
- [ ] **Step 2: Verify build** `cd frontend && npm run build` → sin errores; `python3 scripts/check_hooks.py` → OK.
- [ ] **Step 3: Verify in the browser** (barrido con Playwright como el del 21 oct): Administrador, Administración, Contabilidad y Gerencia ven el panel sin errores de consola ni 4xx; técnico no lo ve y sí ve «Anotar cobro adicional»; vendedor no entra; captura a 375 px.
- [ ] **Step 4: Commit** `feat(costo): panel Costo del trabajo, plantillas y cobro adicional`

---

### Task 7: QA de punta a punta y cierre

**Files:**
- Modify: `backend/scripts/qa_e2e.py` (sección «21. Costo del trabajo»)

- [ ] **Step 1: Add the QA flow**: sobre el proyecto de Arizona del QA — aplicar «Pedestal (rebate) con personal propio» con precio 4.200, aprobar con otra persona, anotar mano de obra 600 y representante 800, el técnico anota extra de 150 en efectivo, Administración lo marca recibido, `job-costing` cuadra (ingreso incluye 150, costo incluye 600 + 800 + material entregado), el técnico recibe 403 en `job-costing` y 404 en obra ajena.
- [ ] **Step 2: Run** `cd backend && .venv/bin/python -m scripts.qa_e2e` → todos los pasos OK.
- [ ] **Step 3: Full checks** `pytest -q --cov=app --cov-fail-under=70`, `pip-audit -r requirements.txt`, `cd frontend && npm audit --omit=dev --audit-level=moderate && npm run build` → todo en verde.
- [ ] **Step 4: Commit** `test(qa): costo del trabajo en el QA de punta a punta`
