"""Costo del trabajo (spec 2026-10-22): plantillas de costo y estimado.

Aldo arma el estimado de un trabajo antes de hacerlo y, al final, lo compara
con lo real. Una **plantilla** reparte el precio del trabajo por concepto, por %
(«Trabajo particular ideal»: 40% de ganancia, 10% permisos, 30% materiales, 20%
mano de obra) o por monto fijo (los pedestales de rebate con sus cifras reales).
Aplicarla llena el presupuesto en borrador; después se ajusta a mano, porque
cada trabajo es distinto.
"""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.billing.money import ZERO, to_money
from app.modules.warehouse import budgets as budget_svc
from app.modules.field_ops.clock import org_today
from app.modules.warehouse.catalogs import (
    BUDGET_CATEGORIES,
    COST_ENTRY_CATEGORIES,
    TARGET_PROFIT,
    TEMPLATE_APPLIES_TO,
    TEMPLATE_CATEGORIES,
    TEMPLATE_MODES,
)
from app.modules.warehouse.models import (
    CostTemplate,
    CostTemplateLine,
    ProjectBudget,
    ProjectBudgetLine,
    ProjectCostEntry,
)
from app.shared.audit import record_audit_event
from app.shared.errors import ConflictError, InvalidInputError, NotFoundError

# Las tres plantillas con las que arranca cada organización (spec §4.2). Las del
# pedestal son las cifras reales que dio el cliente sobre un precio de 4.200.
DEFAULT_TEMPLATES: list[dict] = [
    {"name": "Trabajo particular ideal", "job_type": "Particular", "applies_to": "particular", "lines": [
        {"category": TARGET_PROFIT, "description": "Ganancia mínima", "mode": "percent", "value": "40"},
        {"category": "permit", "description": "Permisos (ciudad, construcción)", "mode": "percent", "value": "10"},
        {"category": "materials", "description": "Materiales", "mode": "percent", "value": "30"},
        {"category": "labor", "description": "Mano de obra", "mode": "percent", "value": "20"},
    ]},
    {"name": "Pedestal (rebate) con personal propio", "job_type": "Pedestal", "applies_to": "rebate", "lines": [
        {"category": "sales_rep", "description": "Representante de ventas", "mode": "amount", "value": "800"},
        {"category": "permit", "description": "Permisos", "mode": "amount", "value": "238"},
        {"category": "materials", "description": "Materiales", "mode": "amount", "value": "1062"},
        {"category": "labor", "description": "Pago al instalador (nómina)", "mode": "amount", "value": "600"},
    ]},
    {"name": "Pedestal (rebate) con subcontratista", "job_type": "Pedestal", "applies_to": "rebate", "lines": [
        {"category": "sales_rep", "description": "Representante de ventas", "mode": "amount", "value": "800"},
        {"category": "permit", "description": "Permisos", "mode": "amount", "value": "230"},
        {"category": "materials", "description": "Materiales", "mode": "amount", "value": "1070"},
        {"category": "contractor", "description": "Pago al contratista", "mode": "amount", "value": "1050"},
    ]},
]


# ---------------------------------------------------------------------------
# Plantillas
# ---------------------------------------------------------------------------

def templates_stmt(organization_id, *, active: bool | None = None):
    stmt = select(CostTemplate).where(CostTemplate.organization_id == organization_id)
    if active is not None:
        stmt = stmt.where(CostTemplate.active == active)
    return stmt.order_by(CostTemplate.name)


async def ensure_default_templates(db: AsyncSession, organization_id) -> None:
    """Siembra las plantillas iniciales la primera vez que la organización las
    pide; si ya tiene alguna (aunque las haya cambiado o borrado), no toca nada."""
    hay = (await db.execute(select(CostTemplate.id).where(
        CostTemplate.organization_id == organization_id).limit(1))).first()
    if hay:
        return
    for plantilla in DEFAULT_TEMPLATES:
        t = CostTemplate(organization_id=organization_id, name=plantilla["name"], job_type=plantilla["job_type"],
                         applies_to=plantilla["applies_to"], active=True)
        db.add(t)
        await db.flush()
        for posicion, linea in enumerate(plantilla["lines"]):
            db.add(CostTemplateLine(template_id=t.id, category=linea["category"],
                                    description=linea["description"], mode=linea["mode"],
                                    value=Decimal(linea["value"]), sort_order=posicion))
    await db.commit()


async def get_template(db: AsyncSession, organization_id, template_id) -> CostTemplate:
    t = await db.get(CostTemplate, template_id)
    if t is None or t.organization_id != organization_id:
        raise NotFoundError("La plantilla no existe.", code="cost_template_not_found")
    return t


async def template_lines_of(db: AsyncSession, template_ids) -> dict:
    ids = list(template_ids)
    if not ids:
        return {}
    agrupadas: dict = {}
    for linea in (await db.execute(select(CostTemplateLine).where(CostTemplateLine.template_id.in_(ids))
                                   .order_by(CostTemplateLine.sort_order))).scalars().all():
        agrupadas.setdefault(linea.template_id, []).append(linea)
    return agrupadas


async def target_profit_of(db: AsyncSession, template_ids) -> dict:
    """{template_id: % de ganancia objetivo} de las plantillas que lo tienen."""
    return {tid: to_money(l.value)
            for tid, lineas in (await template_lines_of(db, template_ids)).items()
            for l in lineas if l.category == TARGET_PROFIT and l.mode == "percent"}


def _clean_lines(lineas: list[dict]) -> list[dict]:
    limpias = []
    for posicion, linea in enumerate(lineas):
        categoria = (linea.get("category") or "").strip()
        if categoria not in TEMPLATE_CATEGORIES:
            raise InvalidInputError(f"«{categoria}» no es una categoría de plantilla.",
                                    code="invalid_template_category")
        modo = (linea.get("mode") or "amount").strip()
        if modo not in TEMPLATE_MODES:
            raise InvalidInputError("Cada renglón es un porcentaje o un monto fijo.", code="invalid_template_mode")
        if categoria == TARGET_PROFIT and modo != "percent":
            raise InvalidInputError("La ganancia objetivo va en porcentaje.", code="invalid_template_mode")
        valor = to_money(linea.get("value") or ZERO)
        if valor < ZERO or (modo == "percent" and valor > Decimal("100")):
            raise InvalidInputError("Un porcentaje va de 0 a 100 y un monto no puede ser negativo.",
                                    code="invalid_template_value")
        descripcion = (linea.get("description") or "").strip() or TEMPLATE_CATEGORIES[categoria]
        limpias.append({"category": categoria, "description": descripcion[:255], "mode": modo,
                        "value": valor, "sort_order": posicion})
    porcentaje = sum((l["value"] for l in limpias if l["mode"] == "percent"), ZERO)
    if porcentaje > Decimal("100"):
        raise InvalidInputError("Los porcentajes de la plantilla suman más de 100%.", code="template_over_100")
    return limpias


async def save_template(db: AsyncSession, *, organization_id, user, data: dict, template_id=None) -> CostTemplate:
    nombre = (data.get("name") or "").strip()
    if not nombre:
        raise InvalidInputError("La plantilla necesita un nombre.", code="template_name_required")
    aplica = data.get("applies_to") or "both"
    if aplica not in TEMPLATE_APPLIES_TO:
        raise InvalidInputError("La plantilla aplica a rebate, particular o ambos.", code="invalid_applies_to")
    lineas = _clean_lines(data.get("lines") or [])
    repetida = select(CostTemplate.id).where(CostTemplate.organization_id == organization_id,
                                             CostTemplate.name == nombre)
    if template_id is not None:
        repetida = repetida.where(CostTemplate.id != template_id)
    if (await db.execute(repetida)).first():
        raise ConflictError("Ya hay una plantilla con ese nombre.", code="template_duplicate")

    if template_id is not None:
        t = await get_template(db, organization_id, template_id)
    else:
        t = CostTemplate(organization_id=organization_id)
        db.add(t)
    t.name, t.job_type, t.applies_to = nombre[:120], (data.get("job_type") or "").strip() or None, aplica
    t.active = bool(data.get("active", True))
    await db.flush()
    for previa in (await template_lines_of(db, [t.id])).get(t.id, []):
        await db.delete(previa)
    await db.flush()
    for linea in lineas:
        db.add(CostTemplateLine(template_id=t.id, **linea))
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cost_template.saved", entity_type="cost_template", entity_id=str(t.id),
                             after_data={"name": t.name, "renglones": len(lineas)})
    await db.commit()
    await db.refresh(t)
    return t


async def delete_template(db: AsyncSession, *, organization_id, user, template_id) -> None:
    t = await get_template(db, organization_id, template_id)
    usada = (await db.execute(select(ProjectBudget.id).where(ProjectBudget.template_id == t.id).limit(1))).first()
    if usada:
        # Un estimado ya armado con ella la nombra: se desactiva en vez de borrarse.
        t.active = False
    else:
        await db.delete(t)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cost_template.deleted", entity_type="cost_template", entity_id=str(t.id),
                             after_data={"name": t.name, "desactivada": bool(usada)})
    await db.commit()


def template_out(t: CostTemplate, lineas: list[CostTemplateLine]) -> dict:
    return {
        "id": str(t.id), "name": t.name, "job_type": t.job_type, "applies_to": t.applies_to,
        "applies_to_label": TEMPLATE_APPLIES_TO.get(t.applies_to), "active": t.active,
        "lines": [{"category": l.category, "category_label": TEMPLATE_CATEGORIES.get(l.category, l.category),
                   "description": l.description, "mode": l.mode, "value": str(to_money(l.value))}
                  for l in lineas],
    }


async def templates_out(db: AsyncSession, plantillas: list[CostTemplate]) -> list[dict]:
    lineas = await template_lines_of(db, [t.id for t in plantillas])
    return [template_out(t, lineas.get(t.id, [])) for t in plantillas]


# ---------------------------------------------------------------------------
# Estimado
# ---------------------------------------------------------------------------

async def is_rebate(db: AsyncSession, project) -> bool:
    """Un trabajo es de rebate cuando su expediente tiene programa."""
    if project.case_id is None:
        return False
    from app.modules.cases.models import Case

    caso = await db.get(Case, project.case_id)
    return caso is not None and caso.program_id is not None


async def default_expected_revenue(db: AsyncSession, organization_id, project) -> Decimal | None:
    """El precio que se espera cobrar si nadie lo escribe.

    En rebate es lo que paga el programa (confirmado por el cliente): la tarifa
    vigente hoy. En un particular, el total de la cotización aceptada del
    proyecto, si la hay.
    """
    from app.modules.billing.models import Quote
    from app.modules.billing.program_config import rate_for
    from app.modules.cases.models import Case

    if project.case_id is not None:
        caso = await db.get(Case, project.case_id)
        if caso is not None and caso.program_id is not None:
            tarifa = await rate_for(db, organization_id=organization_id, program_id=caso.program_id,
                                    on=await org_today(db, organization_id))
            return to_money(tarifa.amount) if tarifa else None
    from sqlalchemy.orm import selectinload

    cotizacion = (await db.execute(select(Quote).options(selectinload(Quote.lines)).where(
        Quote.organization_id == organization_id, Quote.project_id == project.id, Quote.status == "accepted",
    ).order_by(Quote.created_at.desc()))).scalars().first()
    return to_money(cotizacion.total) if cotizacion else None


async def apply_template(db: AsyncSession, *, organization_id, user, budget_id, template_id,
                         expected_revenue=None) -> ProjectBudget:
    """Llena el borrador con la plantilla.

    Reemplaza los renglones escritos a mano; los que vienen del catálogo (una
    lista de materiales aplicada) se quedan, porque son el material real que se
    va a sacar. `percent` reparte el precio; `amount` es el monto tal cual.
    """
    budget = await budget_svc.get_budget(db, organization_id, budget_id)
    budget_svc._editable(budget)
    plantilla = await get_template(db, organization_id, template_id)
    lineas = (await template_lines_of(db, [plantilla.id])).get(plantilla.id, [])

    precio = budget_svc._precio(expected_revenue)
    if precio is None:
        precio = budget.expected_revenue
    if precio is None:
        precio = await default_expected_revenue(
            db, organization_id, await budget_svc.get_project(db, organization_id, budget.project_id))
    usa_porcentaje = any(l.mode == "percent" and l.category != TARGET_PROFIT for l in lineas)
    if usa_porcentaje and precio is None:
        raise InvalidInputError("Esta plantilla reparte el precio por porcentaje: escribe el precio esperado.",
                                code="expected_revenue_required")

    previos = (await budget_svc.budget_lines_of(db, organization_id, [budget.id])).get(budget.id, [])
    conservados = [r for r in previos if r.item_id is not None]
    for renglon in previos:
        if renglon.item_id is None:
            await db.delete(renglon)
    await db.flush()
    posicion = len(conservados)
    for linea in lineas:
        if linea.category == TARGET_PROFIT:
            continue
        monto = to_money(precio * linea.value / Decimal("100")) if linea.mode == "percent" else to_money(linea.value)
        db.add(ProjectBudgetLine(organization_id=organization_id, budget_id=budget.id, category=linea.category,
                                 description=linea.description, quantity=Decimal("1"), unit="unit",
                                 unit_cost=monto, amount=monto, sort_order=posicion))
        posicion += 1
    budget.template_id = plantilla.id
    budget.expected_revenue = to_money(precio) if precio is not None else None
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="budget.template_applied", entity_type="project_budget",
                             entity_id=str(budget.id),
                             after_data={"template": plantilla.name,
                                         "expected_revenue": str(budget.expected_revenue)
                                         if budget.expected_revenue is not None else None})
    await db.commit()
    await db.refresh(budget)
    return budget


# ---------------------------------------------------------------------------
# Costos reales anotados a mano
# ---------------------------------------------------------------------------

async def get_cost_entry(db: AsyncSession, organization_id, project_id, entry_id) -> ProjectCostEntry:
    e = await db.get(ProjectCostEntry, entry_id)
    if e is None or e.organization_id != organization_id or e.project_id != project_id:
        raise NotFoundError("Ese costo no existe.", code="cost_entry_not_found")
    return e


def cost_entries_stmt(organization_id, project_id):
    return select(ProjectCostEntry).where(ProjectCostEntry.organization_id == organization_id,
                                          ProjectCostEntry.project_id == project_id) \
        .order_by(ProjectCostEntry.entry_date.desc(), ProjectCostEntry.created_at.desc())


async def _person(db: AsyncSession, organization_id, user_id):
    from app.modules.users.models import User, UserStatus

    persona = await db.get(User, user_id)
    if persona is None or persona.organization_id != organization_id or persona.status != UserStatus.active:
        raise InvalidInputError("La persona no existe o no está activa.", code="invalid_cost_person")
    return persona


async def save_cost_entry(db: AsyncSession, *, organization_id, user, project_id, data: dict,
                          entry_id=None) -> ProjectCostEntry:
    """La mano de obra del técnico o del subcontratista, o el pago del
    representante: lo que en Housecall Pro es «Labor». Interno: el cliente nunca
    lo ve. Cada trabajo elige si el pago de Luis va como `sales_rep` o `labor`."""
    project = await budget_svc.get_project(db, organization_id, project_id)
    categoria = (data.get("category") or "").strip()
    if categoria not in COST_ENTRY_CATEGORIES:
        raise InvalidInputError(f"«{categoria}» no es una categoría de costo.", code="invalid_cost_category")
    monto = to_money(data.get("amount") or ZERO)
    if monto <= ZERO:
        raise InvalidInputError("El costo tiene que ser mayor que cero.", code="invalid_cost_amount")
    descripcion = (data.get("description") or "").strip() or BUDGET_CATEGORIES[categoria]
    persona_id = data.get("person_user_id")
    if persona_id:
        await _person(db, organization_id, persona_id)
    if entry_id is not None:
        e = await get_cost_entry(db, organization_id, project.id, entry_id)
    else:
        e = ProjectCostEntry(organization_id=organization_id, project_id=project.id, created_by_user_id=user.id)
        db.add(e)
    e.entry_date = data.get("entry_date") or await org_today(db, organization_id)
    e.category, e.description, e.amount = categoria, descripcion[:255], monto
    e.person_user_id = persona_id or None
    e.person_name = (data.get("person_name") or "").strip()[:255] or None
    e.notes = (data.get("notes") or "").strip() or None
    await db.flush()
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cost_entry.saved", entity_type="project_cost_entry", entity_id=str(e.id),
                             after_data={"project_id": str(project.id), "category": categoria, "amount": str(monto)})
    await db.commit()
    await db.refresh(e)
    return e


async def delete_cost_entry(db: AsyncSession, *, organization_id, user, project_id, entry_id) -> None:
    e = await get_cost_entry(db, organization_id, project_id, entry_id)
    await record_audit_event(db, organization_id=organization_id, actor_user_id=user.id,
                             action="cost_entry.deleted", entity_type="project_cost_entry", entity_id=str(e.id),
                             before_data={"category": e.category, "amount": str(e.amount)})
    await db.delete(e)
    await db.commit()


async def cost_entries_out(db: AsyncSession, entradas: list[ProjectCostEntry]) -> list[dict]:
    from app.modules.users.models import User

    ids = {e.person_user_id for e in entradas if e.person_user_id}
    nombres = {u.id: u.full_name for u in (await db.execute(select(User).where(User.id.in_(ids)))).scalars()} \
        if ids else {}
    return [{
        "id": str(e.id), "project_id": str(e.project_id), "entry_date": e.entry_date.isoformat(),
        "category": e.category, "category_label": BUDGET_CATEGORIES.get(e.category, e.category),
        "description": e.description, "amount": str(to_money(e.amount)),
        "person_user_id": str(e.person_user_id) if e.person_user_id else None,
        "person_name": nombres.get(e.person_user_id) or e.person_name, "notes": e.notes,
    } for e in entradas]


async def cost_entries_by_category(db: AsyncSession, organization_id, project_ids: set) -> dict:
    """{project_id: {categoría: Decimal}} de lo anotado a mano."""
    if not project_ids:
        return {}
    resultado: dict = {}
    for e in (await db.execute(select(ProjectCostEntry).where(
            ProjectCostEntry.organization_id == organization_id,
            ProjectCostEntry.project_id.in_(project_ids)))).scalars().all():
        por = resultado.setdefault(e.project_id, {})
        por[e.category] = to_money(por.get(e.category, ZERO) + e.amount)
    return resultado
