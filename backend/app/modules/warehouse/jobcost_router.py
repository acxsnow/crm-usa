"""Rutas del costo del trabajo (spec 2026-10-22): plantillas de costo y
estimado. El técnico no ve nada de esto: son costos y ganancia."""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.users.models import User
from app.modules.warehouse import budgets as budget_svc
from app.modules.warehouse import jobcost as svc
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["job-costing"])

_view = require_any_permission("budgets.manage", "budgets.approve", "warehouse.read")
_manage = require_permission("budgets.manage")


class TemplateLineIn(BaseModel):
    category: str = Field(max_length=30)
    description: str | None = Field(default=None, max_length=255)
    mode: str = "amount"
    value: str = "0"


class TemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    job_type: str | None = Field(default=None, max_length=100)
    applies_to: str = "both"
    active: bool = True
    lines: list[TemplateLineIn] = Field(default_factory=list, max_length=50)


class ApplyTemplateIn(BaseModel):
    template_id: uuid.UUID
    expected_revenue: str | None = None


@router.get("/warehouse/cost-templates")
async def list_templates(response: Response, active: bool | None = None, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         pag: tuple[int, int] = Depends(pagination_params),
                         current_user: User = Depends(_view)) -> list[dict]:
    await svc.ensure_default_templates(db, organization_id)
    plantillas = await paginate(db, svc.templates_stmt(organization_id, active=active),
                                limit=pag[0], offset=pag[1], response=response)
    return await svc.templates_out(db, plantillas)


@router.post("/warehouse/cost-templates", status_code=201)
async def create_template(payload: TemplateIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    t = await svc.save_template(db, organization_id=organization_id, user=current_user, data=payload.model_dump())
    return (await svc.templates_out(db, [t]))[0]


@router.put("/warehouse/cost-templates/{template_id}")
async def update_template(template_id: uuid.UUID, payload: TemplateIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> dict:
    t = await svc.save_template(db, organization_id=organization_id, user=current_user,
                                data=payload.model_dump(), template_id=template_id)
    return (await svc.templates_out(db, [t]))[0]


@router.delete("/warehouse/cost-templates/{template_id}", status_code=204)
async def delete_template(template_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_manage)) -> None:
    await svc.delete_template(db, organization_id=organization_id, user=current_user, template_id=template_id)


@router.post("/warehouse/budgets/{budget_id}/apply-template")
async def apply_template(budget_id: uuid.UUID, payload: ApplyTemplateIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_manage)) -> dict:
    """Llena el estimado en borrador con la plantilla (por % del precio o por monto)."""
    budget = await svc.apply_template(db, organization_id=organization_id, user=current_user, budget_id=budget_id,
                                      template_id=payload.template_id, expected_revenue=payload.expected_revenue)
    return (await budget_svc.budgets_out(db, organization_id, [budget]))[0]


# ---------------------------------------------------------------------------
# Costos reales anotados a mano
# ---------------------------------------------------------------------------

class CostEntryIn(BaseModel):
    entry_date: date | None = None
    category: str = Field(max_length=30)
    description: str | None = Field(default=None, max_length=255)
    amount: str
    person_user_id: uuid.UUID | None = None
    person_name: str | None = Field(default=None, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/warehouse/projects/{project_id}/cost-entries")
async def list_cost_entries(project_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            pag: tuple[int, int] = Depends(pagination_params),
                            current_user: User = Depends(_view)) -> list[dict]:
    project = await budget_svc.get_project(db, organization_id, project_id)
    entradas = await paginate(db, svc.cost_entries_stmt(organization_id, project.id),
                              limit=pag[0], offset=pag[1], response=response)
    return await svc.cost_entries_out(db, entradas)


@router.post("/warehouse/projects/{project_id}/cost-entries", status_code=201)
async def create_cost_entry(project_id: uuid.UUID, payload: CostEntryIn, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_manage)) -> dict:
    e = await svc.save_cost_entry(db, organization_id=organization_id, user=current_user, project_id=project_id,
                                  data=payload.model_dump())
    return (await svc.cost_entries_out(db, [e]))[0]


@router.put("/warehouse/projects/{project_id}/cost-entries/{entry_id}")
async def update_cost_entry(project_id: uuid.UUID, entry_id: uuid.UUID, payload: CostEntryIn,
                            db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_manage)) -> dict:
    e = await svc.save_cost_entry(db, organization_id=organization_id, user=current_user, project_id=project_id,
                                  data=payload.model_dump(), entry_id=entry_id)
    return (await svc.cost_entries_out(db, [e]))[0]


@router.delete("/warehouse/projects/{project_id}/cost-entries/{entry_id}", status_code=204)
async def delete_cost_entry(project_id: uuid.UUID, entry_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_manage)) -> None:
    await svc.delete_cost_entry(db, organization_id=organization_id, user=current_user, project_id=project_id,
                                entry_id=entry_id)


# ---------------------------------------------------------------------------
# Cobros adicionales
# ---------------------------------------------------------------------------

_extra = require_any_permission("daylogs.manage", "budgets.manage", "budgets.approve", "warehouse.read")
# Anotar un cobro: el técnico en la obra o la oficina; leer bodega no alcanza.
_extra_write = require_any_permission("daylogs.manage", "budgets.manage")


class ExtraChargeIn(BaseModel):
    charge_date: date | None = None
    description: str = Field(default="", max_length=255)
    amount: str
    payment_method: str = "cash"
    received_by_user_id: uuid.UUID | None = None


@router.get("/warehouse/projects/{project_id}/extra-charges")
async def list_extra_charges(project_id: uuid.UUID, response: Response, db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             pag: tuple[int, int] = Depends(pagination_params),
                             current_user: User = Depends(_extra)) -> list[dict]:
    """La oficina ve todos los de la obra; el técnico, solo los que cobró él."""
    from app.modules.field_ops.access import get_visible_project

    project = await get_visible_project(db, organization_id=organization_id, user=current_user,
                                        project_id=project_id)
    stmt = svc.extra_charges_stmt(organization_id, project_id=project.id,
                                  own_user_id=None if svc.sees_all(current_user) else current_user.id)
    cobros = await paginate(db, stmt, limit=pag[0], offset=pag[1], response=response)
    return await svc.extra_charges_out(db, cobros)


@router.post("/warehouse/projects/{project_id}/extra-charges", status_code=201)
async def create_extra_charge(project_id: uuid.UUID, payload: ExtraChargeIn, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_extra_write)) -> dict:
    c = await svc.create_extra_charge(db, organization_id=organization_id, user=current_user,
                                      project_id=project_id, data=payload.model_dump())
    return (await svc.extra_charges_out(db, [c]))[0]


@router.get("/warehouse/extra-charges/pending")
async def pending_extra_charges(response: Response, db: AsyncSession = Depends(get_db),
                                organization_id: uuid.UUID = Depends(get_organization_id),
                                pag: tuple[int, int] = Depends(pagination_params),
                                current_user: User = Depends(_manage)) -> list[dict]:
    """El efectivo que los técnicos cobraron y todavía no llega a la oficina."""
    cobros = await paginate(db, svc.extra_charges_stmt(organization_id, pending_only=True),
                            limit=pag[0], offset=pag[1], response=response)
    return await svc.extra_charges_out(db, cobros)


@router.post("/warehouse/extra-charges/{charge_id}/deliver")
async def deliver_extra_charge(charge_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                               organization_id: uuid.UUID = Depends(get_organization_id),
                               current_user: User = Depends(_manage)) -> dict:
    c = await svc.mark_delivered(db, organization_id=organization_id, user=current_user, charge_id=charge_id)
    return (await svc.extra_charges_out(db, [c]))[0]


@router.get("/warehouse/projects/{project_id}/job-costing")
async def get_job_costing(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_view)) -> dict:
    """El costo del trabajo: ingreso, costo real por concepto, estimado y margen."""
    from app.modules.warehouse import costing

    project = await budget_svc.get_project(db, organization_id, project_id)
    return await costing.job_costing(db, organization_id=organization_id, project_id=project.id)
