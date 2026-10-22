"""Presupuesto del proyecto (punto 3 del cuestionario del 19 de octubre).

El supervisor estima antes de instalar y lo aprueba; de ahí en adelante ese
presupuesto es la referencia contra la que se compara lo que de verdad costó la
obra (`costing.py`). El presupuesto se puede armar a mano o copiando una lista
predefinida del tipo de trabajo (punto 2), que es el caso normal: «un aire lleva
esto», y el supervisor ajusta cantidades.

Dos reglas sostienen el archivo:

- **Un presupuesto aprobado no se edita.** Para cambiarlo se aprueba otro, y el
  anterior queda `reemplazado`. Un estimado que cambia después de aprobado no
  sirve como referencia de nada.
- **El monto se guarda, no se recalcula.** El presupuesto es lo que se aprobó:
  corregir el costo del catálogo en marzo no puede cambiar lo que se aprobó en
  enero.
"""
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.field_ops.models import Project
from app.modules.warehouse import service as wh
from app.modules.warehouse.catalogs import BUDGET_CATEGORIES, ITEM_UNITS, BudgetStatus
from app.modules.warehouse.kits import get_kit, kit_items_of
from app.modules.warehouse.models import (
    ProjectBudget,
    ProjectBudgetLine,
    WarehouseItem,
)
from app.shared.audit import record_audit_event
from app.shared.errors import InvalidInputError, NotFoundError

Q2 = Decimal("0.01")


def _q(value) -> Decimal:
    return (Decimal(str(value)) if value is not None else ZERO).quantize(Q2)


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lectura
# ---------------------------------------------------------------------------

async def get_project(db: AsyncSession, organization_id, project_id) -> Project:
    """El proyecto de esta organización. El presupuesto cuelga de la obra, así
    que la obra tiene que ser de la misma organización que lo está armando."""
    project = await db.get(Project, project_id)
    if project is None or project.organization_id != organization_id:
        raise NotFoundError("El proyecto no existe.", code="project_not_found")
    return project


async def get_budget(db: AsyncSession, organization_id, budget_id) -> ProjectBudget:
    budget = await db.get(ProjectBudget, budget_id)
    if budget is None or budget.organization_id != organization_id:
        raise NotFoundError("El presupuesto no existe.", code="budget_not_found")
    return budget


async def budget_lines_of(db: AsyncSession, organization_id, budget_ids) -> dict:
    """Renglones de varios presupuestos, agrupados. Se leen aparte porque la
    relación está en `lazy="raise"`."""
    ids = list(budget_ids)
    if not ids:
        return {}
    filas = (await db.execute(select(ProjectBudgetLine).where(
        ProjectBudgetLine.organization_id == organization_id,
        ProjectBudgetLine.budget_id.in_(ids),
    ).order_by(ProjectBudgetLine.sort_order, ProjectBudgetLine.created_at))).scalars().all()
    agrupados: dict = {}
    for renglon in filas:
        agrupados.setdefault(renglon.budget_id, []).append(renglon)
    return agrupados


def budgets_stmt(organization_id, *, project_id=None, status: str | None = None):
    stmt = select(ProjectBudget).where(ProjectBudget.organization_id == organization_id)
    if project_id:
        stmt = stmt.where(ProjectBudget.project_id == project_id)
    if status:
        stmt = stmt.where(ProjectBudget.status == status)
    return stmt.order_by(ProjectBudget.created_at.desc())


async def current_budget(db: AsyncSession, organization_id, project_id) -> ProjectBudget | None:
    """El presupuesto vigente de la obra: el aprobado si lo hay, y si no el
    borrador más reciente. Es el que la pantalla del proyecto abre por defecto."""
    aprobado = (await db.execute(select(ProjectBudget).where(
        ProjectBudget.organization_id == organization_id,
        ProjectBudget.project_id == project_id,
        ProjectBudget.status == BudgetStatus.APROBADO,
    ))).scalars().first()
    if aprobado is not None:
        return aprobado
    return (await db.execute(select(ProjectBudget).where(
        ProjectBudget.organization_id == organization_id,
        ProjectBudget.project_id == project_id,
    ).order_by(ProjectBudget.created_at.desc()))).scalars().first()


# ---------------------------------------------------------------------------
# Armar el presupuesto
# ---------------------------------------------------------------------------

def _precio(valor) -> Decimal | None:
    """El precio esperado del trabajo: vacío es «sin precio», nunca cero."""
    if valor is None or str(valor).strip() == "":
        return None
    precio = to_money(valor)
    if precio <= ZERO:
        raise InvalidInputError("El precio esperado tiene que ser mayor que cero.", code="invalid_expected_revenue")
    return precio


def _editable(budget: ProjectBudget) -> None:
    if budget.status != BudgetStatus.BORRADOR:
        raise InvalidInputError("Un presupuesto aprobado no se edita: haz uno nuevo y apruébalo.",
                                code="budget_not_editable")


async def _normalizar_renglones(db, organization_id, renglones: list[dict]) -> list[dict]:
    """Cada renglón con su categoría, su artículo (si lo tiene) y su monto.

    Una categoría que no existe se rechaza en vez de caer en «otro»: un renglón
    mal categorizado descuadra la desviación por categoría, que es justo lo que
    se quiere mirar.
    """
    limpios = []
    for posicion, renglon in enumerate(renglones):
        categoria = (renglon.get("category") or "materials").strip()
        if categoria not in BUDGET_CATEGORIES:
            raise InvalidInputError(f"«{categoria}» no es una categoría de presupuesto.",
                                    code="invalid_budget_category")
        item = await wh.get_item(db, organization_id, renglon["item_id"]) if renglon.get("item_id") else None
        descripcion = (renglon.get("description") or "").strip() or (item.name if item else "")
        if not descripcion:
            raise InvalidInputError("Todo renglón del presupuesto necesita una descripción.",
                                    code="budget_line_description_required")
        cantidad = _q(renglon.get("quantity") or Decimal("1"))
        if cantidad <= ZERO:
            raise InvalidInputError(f"«{descripcion}» necesita una cantidad mayor que cero.",
                                    code="invalid_budget_quantity")
        costo = to_money(renglon.get("unit_cost") if renglon.get("unit_cost") is not None
                         else (item.unit_cost if item else ZERO))
        if costo < ZERO:
            raise InvalidInputError(f"«{descripcion}» no puede tener un costo negativo.",
                                    code="invalid_budget_unit_cost")
        limpios.append({
            "category": categoria, "item_id": item.id if item else None, "description": descripcion,
            "quantity": cantidad, "unit": (renglon.get("unit") or (item.unit if item else "unit")),
            "unit_cost": costo, "amount": (cantidad * costo).quantize(Q2),
            "notes": (renglon.get("notes") or "").strip() or None, "sort_order": posicion,
        })
    return limpios


async def save_budget(db: AsyncSession, *, organization_id, user, data: dict,
                      budget_id=None) -> ProjectBudget:
    """Crea o reemplaza el borrador completo, con sus renglones.

    El proyecto no se cambia al editar: cambiar de obra un presupuesto ya armado
    sería mover plata de un proyecto a otro sin que nadie lo note.
    """
    renglones = await _normalizar_renglones(db, organization_id, data.get("lines") or [])
    if budget_id is not None:
        budget = await get_budget(db, organization_id, budget_id)
        _editable(budget)
    else:
        project = await get_project(db, organization_id, data.get("project_id"))
        budget = ProjectBudget(organization_id=organization_id, project_id=project.id,
                               created_by_user_id=user.id)
        db.add(budget)
    budget.notes = (data.get("notes") or "").strip() or None
    if "expected_revenue" in data:
        budget.expected_revenue = _precio(data.get("expected_revenue"))
    await db.flush()

    for previo in (await budget_lines_of(db, organization_id, [budget.id])).get(budget.id, []):
        await db.delete(previo)
    await db.flush()
    for renglon in renglones:
        db.add(ProjectBudgetLine(organization_id=organization_id, budget_id=budget.id, **renglon))
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="budget.saved", entity_type="project_budget",
                             entity_id=str(budget.id),
                             after_data={"project_id": str(budget.project_id), "renglones": len(renglones)})
    await db.commit()
    await db.refresh(budget)
    return budget


async def apply_kit(db: AsyncSession, *, organization_id, user, budget_id, kit_id) -> dict:
    """Copia los renglones de una lista predefinida al borrador del presupuesto.

    El material entra como `materials` y el equipo como `equipment`, con el costo
    del catálogo; el supervisor después ajusta cantidades y agrega la mano de
    obra, que la lista no trae. Lo que ya estaba (mismo artículo) no se repite.
    """
    budget = await get_budget(db, organization_id, budget_id)
    _editable(budget)
    kit = await get_kit(db, organization_id, kit_id)
    renglones = (await kit_items_of(db, organization_id, [kit.id])).get(kit.id, [])
    if not renglones:
        raise InvalidInputError(f"«{kit.name}» todavía no tiene material.", code="empty_kit")

    previos = (await budget_lines_of(db, organization_id, [budget.id])).get(budget.id, [])
    ya_estan = {l.item_id for l in previos if l.item_id is not None}
    posicion = len(previos)
    agregadas = 0
    for renglon in renglones:
        if renglon.item_id in ya_estan:
            continue
        item = await wh.get_item(db, organization_id, renglon.item_id)
        cantidad = _q(renglon.quantity)
        costo = to_money(item.unit_cost)
        categoria = "equipment" if item.category == "equipment" else "materials"
        db.add(ProjectBudgetLine(
            organization_id=organization_id, budget_id=budget.id, category=categoria,
            item_id=item.id, description=item.name, quantity=cantidad, unit=item.unit,
            unit_cost=costo, amount=(cantidad * costo).quantize(Q2),
            notes=renglon.spec_label, sort_order=posicion,
        ))
        ya_estan.add(item.id)
        posicion += 1
        agregadas += 1
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="budget.kit_applied", entity_type="project_budget",
                             entity_id=str(budget.id),
                             after_data={"kit": kit.name, "agregadas": agregadas})
    await db.commit()
    await db.refresh(budget)
    return {"budget": budget, "kit": kit, "agregadas": agregadas,
            "omitidas": len(renglones) - agregadas}


# ---------------------------------------------------------------------------
# Aprobar
# ---------------------------------------------------------------------------

async def approve_budget(db: AsyncSession, *, organization_id, user, budget_id) -> ProjectBudget:
    """Aprueba el presupuesto y deja como único vigente al de esta obra.

    El anterior no se borra: pasa a `reemplazado`. Si se borrara, un mes después
    nadie podría explicar contra qué se comparó el gasto de la primera semana.
    """
    budget = await get_budget(db, organization_id, budget_id)
    _editable(budget)
    if not (await budget_lines_of(db, organization_id, [budget.id])).get(budget.id):
        raise InvalidInputError("Un presupuesto sin renglones no se aprueba.", code="empty_budget")

    vigentes = (await db.execute(select(ProjectBudget).where(
        ProjectBudget.organization_id == organization_id,
        ProjectBudget.project_id == budget.project_id,
        ProjectBudget.status == BudgetStatus.APROBADO,
        ProjectBudget.id != budget.id,
    ))).scalars().all()
    for anterior in vigentes:
        anterior.status = BudgetStatus.REEMPLAZADO

    budget.status = BudgetStatus.APROBADO
    budget.approved_by_user_id = user.id
    budget.approved_at = _now()
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="budget.approved", entity_type="project_budget",
                             entity_id=str(budget.id),
                             after_data={"project_id": str(budget.project_id), "reemplazados": len(vigentes)})
    await db.commit()
    await db.refresh(budget)
    return budget


async def delete_budget(db: AsyncSession, *, organization_id, user, budget_id) -> None:
    """Solo se borra un borrador: el aprobado o el reemplazado son historial."""
    budget = await get_budget(db, organization_id, budget_id)
    _editable(budget)
    await db.delete(budget)
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="budget.deleted", entity_type="project_budget",
                             entity_id=str(budget_id), after_data={"project_id": str(budget.project_id)})
    await db.commit()


# ---------------------------------------------------------------------------
# Salidas para las pantallas
# ---------------------------------------------------------------------------

def budget_line_out(renglon: ProjectBudgetLine, *, item: WarehouseItem | None = None) -> dict:
    return {
        "id": str(renglon.id), "category": renglon.category,
        "item_id": str(renglon.item_id) if renglon.item_id else None,
        "item_name": item.name if item else None, "sku": item.sku if item else None,
        "description": renglon.description,
        "quantity": str(_q(renglon.quantity)),
        "unit": renglon.unit, "unit_label": ITEM_UNITS.get(renglon.unit, renglon.unit),
        "unit_cost": str(to_money(renglon.unit_cost)),
        "amount": str(to_money(renglon.amount)),
        "notes": renglon.notes,
    }


def _pct(parte: Decimal, base: Decimal) -> float | None:
    if base is None or base <= ZERO:
        return None
    return float((parte / base * 100).quantize(Decimal("0.1")))


def estimate_summary(budget: ProjectBudget, total_cost: Decimal, target_profit_pct: Decimal | None) -> dict:
    """Lo que el estimado promete: precio, ganancia esperada y margen, y si queda
    por debajo de la ganancia objetivo de su plantilla. La ganancia no es un
    renglón: es lo que sobra del precio."""
    precio = to_money(budget.expected_revenue) if budget.expected_revenue is not None else None
    ganancia = to_money(precio - total_cost) if precio is not None else None
    margen = _pct(ganancia, precio) if precio is not None else None
    objetivo = float(target_profit_pct) if target_profit_pct is not None else None
    return {
        "expected_revenue": str(precio) if precio is not None else None,
        "expected_profit": str(ganancia) if ganancia is not None else None,
        "expected_margin_pct": margen,
        "target_profit_pct": objetivo,
        "below_target": margen is not None and objetivo is not None and margen < objetivo,
    }


def budget_out(budget: ProjectBudget, renglones: list[ProjectBudgetLine], *,
               items: dict | None = None, totals: dict | None = None,
               target_profit_pct: Decimal | None = None) -> dict:
    catalogo = items or {}
    total = to_money((totals or {}).get("total", ZERO))
    return {
        **estimate_summary(budget, total, target_profit_pct),
        "template_id": str(budget.template_id) if budget.template_id else None,
        "id": str(budget.id), "project_id": str(budget.project_id), "status": budget.status,
        "notes": budget.notes,
        "created_at": budget.created_at.isoformat() if budget.created_at else None,
        "approved_at": budget.approved_at.isoformat() if budget.approved_at else None,
        "approved_by_user_id": str(budget.approved_by_user_id) if budget.approved_by_user_id else None,
        "total": str(total),
        "by_category": {c: str(to_money(v)) for c, v in (totals or {}).get("by_category", {}).items()},
        "lines": [budget_line_out(r, item=catalogo.get(r.item_id)) for r in renglones],
    }


async def budgets_out(db: AsyncSession, organization_id, budgets: list[ProjectBudget]) -> list[dict]:
    """Presupuestos con sus renglones y totales, en pocas consultas."""
    if not budgets:
        return []
    agrupados = await budget_lines_of(db, organization_id, [b.id for b in budgets])
    item_ids = {r.item_id for rs in agrupados.values() for r in rs if r.item_id is not None}
    items = {i.id: i for i in (await db.execute(select(WarehouseItem).where(
        WarehouseItem.id.in_(item_ids)))).scalars().all()} if item_ids else {}
    from app.modules.warehouse.jobcost import target_profit_of

    objetivos = await target_profit_of(db, {b.template_id for b in budgets if b.template_id})
    return [budget_out(b, agrupados.get(b.id, []), items=items, totals=budget_totals(agrupados.get(b.id, [])),
                       target_profit_pct=objetivos.get(b.template_id))
            for b in budgets]


def budget_totals(renglones: list[ProjectBudgetLine]) -> dict:
    """Total y total por categoría. Se suma con `to_money` para no arrastrar
    centavos de la aritmética binaria."""
    por_categoria: dict[str, Decimal] = {}
    for renglon in renglones:
        por_categoria[renglon.category] = to_money(por_categoria.get(renglon.category, ZERO) + renglon.amount)
    total = to_money(sum(por_categoria.values(), ZERO))
    return {"total": total, "by_category": por_categoria}
