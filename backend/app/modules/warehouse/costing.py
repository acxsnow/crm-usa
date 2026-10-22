"""Costo real de la obra contra su presupuesto aprobado (punto 3 del cuestionario).

El costo real se arma con tres cosas, y ninguna es «lo que se compró»:

- lo que **salió de bodega** para la obra, valorado a costo del catálogo;
- los **gastos de campo** aprobados de la obra (`expenses`);
- las **compras cargadas directo a la obra**: material o equipo que nunca pasó
  por bodega y por eso es costo desde el primer día.

**D-BOD-2** es la razón de ser de este archivo: lo que entra a bodega es
inventario, no costo de la obra. Por eso una línea de factura cuyo material entró
a bodega **no** se cuenta como compra directa —su costo llega cuando el material
sale— y el mismo material nunca se cuenta dos veces. El vínculo es la clave
`supplier-invoice-line:{id de la línea}` que deja el movimiento de entrada por
compra, la misma forma de `source_key` que ya usan la entrega de una orden
(`release:…`) y el conteo inicial (`initial-count:…`).

La categoría del renglón del presupuesto y la del costo son el mismo texto, así
que la desviación se calcula por categoría sin traducir nada.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.finance.models import SupplierInvoice, SupplierInvoiceLine
from app.modules.finance.profitability import project_costs
from app.modules.field_ops.models import Project, ProjectStatus
from app.modules.warehouse.budgets import budget_lines_of, budget_totals, current_budget
from app.modules.warehouse.catalogs import BUDGET_CATEGORIES, BudgetCategory
from app.modules.warehouse.models import (
    ProjectBudget,
    ProjectBudgetLine,
    WarehouseItem,
    WarehouseMovement,
)
from app.modules.warehouse.service import totals_by_item

# Lo que se compara: las categorías del presupuesto más los gastos de campo, que
# se gastan pero no se presupuestan (nafta, peajes, viáticos).
ACTUAL_LABELS: dict[str, str] = {**BUDGET_CATEGORIES, "field_expenses": "Gastos de campo"}

# La clave con la que el movimiento de entrada por compra marca de qué línea de
# factura vino: es lo que permite no contar el mismo material dos veces.
WAREHOUSE_ENTRY_PREFIX = "supplier-invoice-line:"

# El equipo del catálogo se costea como equipo; todo lo demás es material. Es la
# misma regla con la que la lista predefinida arma un presupuesto.
DEFAULT_BUDGET_CATEGORY = BudgetCategory.MATERIALS
EQUIPMENT_BUDGET_CATEGORY = BudgetCategory.EQUIPMENT


def warehouse_entry_key(invoice_line_id) -> str:
    """La clave de idempotencia de la entrada a bodega de una línea de factura."""
    return f"{WAREHOUSE_ENTRY_PREFIX}{invoice_line_id}"


def _category_of(item_category: str | None) -> str:
    return EQUIPMENT_BUDGET_CATEGORY if item_category == "equipment" else DEFAULT_BUDGET_CATEGORY


# ---------------------------------------------------------------------------
# Lo que salió de bodega
# ---------------------------------------------------------------------------

async def warehouse_costs(db: AsyncSession, organization_id, project_ids: set) -> dict:
    """{project_id: {categoría: Decimal}} de lo entregado a cada obra.

    Se valora a costo del catálogo —el que quedó guardado en el movimiento al
    entregar— y no al precio de venta: la obra se cuesta a lo que costó el
    material, no a lo que se le factura al cliente. Si el movimiento no guardó
    costo (la entrega de una orden no lo escribe), se cae al costo vigente del
    artículo en el catálogo: valorar en cero dejaría al material como gratis.
    """
    costos: dict = {pid: {c: ZERO for c in (BudgetCategory.MATERIALS, BudgetCategory.EQUIPMENT)}
                    for pid in project_ids}
    if not project_ids:
        return costos
    filas = (await db.execute(
        select(WarehouseMovement.project_id, WarehouseItem.category, WarehouseMovement.quantity,
               WarehouseMovement.unit_cost, WarehouseItem.unit_cost)
        .join(WarehouseItem, WarehouseItem.id == WarehouseMovement.item_id)
        .where(WarehouseMovement.organization_id == organization_id,
               WarehouseMovement.project_id.in_(project_ids),
               WarehouseMovement.movement_type == "salida"))).all()
    for project_id, item_category, quantity, unit_cost, catalog_cost in filas:
        costo_unitario = to_money(unit_cost) if unit_cost is not None else to_money(catalog_cost or ZERO)
        costos[project_id][_category_of(item_category)] += to_money(costo_unitario * abs(Decimal(str(quantity))))
    return costos


async def _lines_that_entered_warehouse(db: AsyncSession, organization_id, project_ids: set) -> set:
    """Líneas de factura de la obra cuyo material entró a bodega (D-BOD-2).

    Se buscan por su clave, armada desde el id de la línea, en vez de leer y
    partir el texto de la clave: así la comparación es exacta y no depende del
    formato.
    """
    if not project_ids:
        return set()
    ids = (await db.execute(
        select(SupplierInvoiceLine.id)
        .join(SupplierInvoice, SupplierInvoice.id == SupplierInvoiceLine.invoice_id)
        .where(SupplierInvoice.organization_id == organization_id,
               SupplierInvoice.status != "void",
               SupplierInvoiceLine.project_id.in_(project_ids)))).scalars().all()
    if not ids:
        return set()
    claves = {warehouse_entry_key(line_id): line_id for line_id in ids}
    encontradas = (await db.execute(select(WarehouseMovement.source_key).where(
        WarehouseMovement.organization_id == organization_id,
        WarehouseMovement.source_key.in_(list(claves))))).scalars().all()
    return {claves[clave] for clave in encontradas if clave in claves}


async def project_actual_costs(db: AsyncSession, organization_id, project_ids: set) -> dict:
    """{project_id: {categoría: Decimal}} con el costo real completo de cada obra."""
    costos: dict = {pid: {c: ZERO for c in ACTUAL_LABELS} for pid in project_ids}
    if not project_ids:
        return costos
    en_bodega = await _lines_that_entered_warehouse(db, organization_id, project_ids)
    for project_id, por_categoria in (
            await project_costs(db, organization_id, project_ids, exclude_line_ids=en_bodega)).items():
        for categoria, valor in por_categoria.items():
            if categoria in costos[project_id]:
                costos[project_id][categoria] += to_money(valor)
    for project_id, por_categoria in (await warehouse_costs(db, organization_id, project_ids)).items():
        for categoria, valor in por_categoria.items():
            costos[project_id][categoria] += to_money(valor)
    # Lo anotado a mano: mano de obra, subcontratista, representante (spec 2026-10-22).
    from app.modules.warehouse.jobcost import cost_entries_by_category

    for project_id, por_categoria in (await cost_entries_by_category(db, organization_id, project_ids)).items():
        for categoria, valor in por_categoria.items():
            costos[project_id][categoria] = costos[project_id].get(categoria, ZERO) + to_money(valor)
    return costos


# ---------------------------------------------------------------------------
# Presupuesto contra real
# ---------------------------------------------------------------------------

def _deviation_pct(desviacion: Decimal, estimado: Decimal) -> float | None:
    """Cuánto se fue de lo estimado, en porcentaje. Sin estimado no hay porcentaje
    que calcular: queda nulo y la pantalla muestra el monto."""
    if estimado <= ZERO:
        return None
    return float((desviacion / estimado * 100).quantize(Decimal("0.1")))


async def budget_vs_actual(db: AsyncSession, *, organization_id, project_id) -> dict:
    """Estimado contra real del proyecto, por categoría y en total.

    La desviación es `real − estimado`: positiva quiere decir que se gastó más de
    lo presupuestado. Las categorías salen siempre todas —aunque estén en cero—
    para que la comparación de un mes con otro se lea en las mismas filas.
    """
    real = (await project_actual_costs(db, organization_id, {project_id}))[project_id]
    budget = await current_budget(db, organization_id, project_id)
    renglones = (await budget_lines_of(db, organization_id, [budget.id])).get(budget.id, []) if budget else []
    estimado = budget_totals(renglones)["by_category"]

    filas = []
    total_estimado = ZERO
    total_real = ZERO
    for categoria, etiqueta in ACTUAL_LABELS.items():
        est = to_money(estimado.get(categoria, ZERO))
        act = to_money(real.get(categoria, ZERO))
        desviacion = to_money(act - est)
        filas.append({"category": categoria, "label": etiqueta, "estimated": str(est), "actual": str(act),
                      "deviation": str(desviacion), "deviation_pct": _deviation_pct(desviacion, est)})
        total_estimado += est
        total_real += act
    total_estimado = to_money(total_estimado)
    total_real = to_money(total_real)
    total_desviacion = to_money(total_real - total_estimado)
    return {
        "project_id": str(project_id),
        "budget_id": str(budget.id) if budget else None,
        "budget_status": budget.status if budget else None,
        "rows": filas,
        "totals": {"estimated": str(total_estimado), "actual": str(total_real),
                   "deviation": str(total_desviacion),
                   "deviation_pct": _deviation_pct(total_desviacion, total_estimado)},
    }


# ---------------------------------------------------------------------------
# Compras por adelantado
# ---------------------------------------------------------------------------

async def purchasing_report(db: AsyncSession, organization_id) -> dict:
    """Qué comprar antes de la temporada: lo presupuestado por venir menos lo que
    hay en bodega, artículo por artículo.

    «Por venir» son los presupuestos **aprobados** de obras que todavía no
    terminaron: lo ya instalado no vuelve a comprarse. Se incluye la camioneta en
    la existencia —el material que ya salió de bodega y no se ha consumido sigue
    estando— y el resultado nunca es negativo: sobrar no es comprar.
    """
    pendientes = select(Project.id).where(
        Project.organization_id == organization_id,
        Project.status.not_in((ProjectStatus.completed, ProjectStatus.cancelled)),
    )
    filas = (await db.execute(
        select(ProjectBudgetLine.item_id, ProjectBudgetLine.quantity)
        .where(ProjectBudgetLine.organization_id == organization_id,
               ProjectBudgetLine.budget_id.in_(
                   select(ProjectBudget.id).where(
                       ProjectBudget.organization_id == organization_id,
                       ProjectBudget.status == "aprobado",
                       ProjectBudget.project_id.in_(pendientes))),
               ProjectBudgetLine.item_id.is_not(None)))).all()

    presupuestado: dict = {}
    for item_id, cantidad in filas:
        presupuestado[item_id] = presupuestado.get(item_id, ZERO) + Decimal(str(cantidad))

    existencias = await totals_by_item(db, organization_id, list(presupuestado))
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(list(presupuestado))))).scalars().all()} if presupuestado else {}

    renglones = []
    total_presupuestado = ZERO
    total_por_comprar = ZERO
    for item_id, cantidad in presupuestado.items():
        item = items.get(item_id)
        if item is None:
            continue
        en_bodega = (existencias.get(item_id) or {}).get("total", ZERO)
        por_comprar = cantidad - en_bodega
        if por_comprar < ZERO:
            por_comprar = ZERO
        renglones.append({
            "item_id": str(item_id), "item_name": item.name, "sku": item.sku, "unit": item.unit,
            "budgeted": str(to_money(cantidad)), "in_stock": str(to_money(en_bodega)),
            "to_buy": str(to_money(por_comprar)),
            "unit_cost": str(to_money(item.unit_cost)),
            "estimated_cost": str(to_money(por_comprar * to_money(item.unit_cost))),
            "below_minimum": item.min_quantity is not None and to_money(en_bodega) <= to_money(item.min_quantity),
        })
        total_presupuestado += to_money(cantidad)
        total_por_comprar += to_money(por_comprar)
    renglones.sort(key=lambda r: (r["to_buy"] == "0.00", r["item_name"] or ""))
    return {"rows": renglones, "totals": {"budgeted": str(to_money(total_presupuestado)),
                                          "to_buy": str(to_money(total_por_comprar)),
                                          "items": len(renglones)}}
