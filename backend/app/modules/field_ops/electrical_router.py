"""Rutas de la inspección eléctrica (cliente, 5 nov 2026). Ver `electrical.py`."""
import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_any_permission, require_permission
from app.db.session import get_db
from app.modules.field_ops import electrical as svc
from app.modules.users.models import User
from app.shared.pagination import paginate, paginate_list, pagination_params

router = APIRouter()

_ver = require_any_permission("dispatch.manage", "cases.review", "cases.read_all", "checklists.complete")


class ElectricalInspectionCreate(BaseModel):
    technician_user_id: uuid.UUID
    scheduled_date: date
    notes: str | None = Field(None, max_length=2000)


class ElectricalInspectionResult(BaseModel):
    viability: str
    panel_amperage: str | None = None
    tons: Decimal | None = None
    water_heater_eligible: bool | None = None
    induction_eligible: bool | None = None
    result_notes: str | None = Field(None, max_length=4000)


class ElectricalInspectionCancel(BaseModel):
    reason: str = Field(..., max_length=1000)


class ElectricalInspectionResponse(BaseModel):
    id: uuid.UUID
    case_id: uuid.UUID
    case_number: str | None = None
    address: str | None = None
    customer_name: str | None = None
    technician_user_id: uuid.UUID
    technician_name: str | None = None
    scheduled_date: date
    status: str
    status_label: str
    notes: str | None
    panel_amperage: str | None
    viability: str | None
    viability_label: str | None
    tons: Decimal | None
    water_heater_eligible: bool | None
    induction_eligible: bool | None
    result_notes: str | None
    completed_at: datetime | None
    cancel_reason: str | None


async def _out(db, filas) -> list[ElectricalInspectionResponse]:
    """`filas`: (inspección, expediente o None)."""
    from app.modules.crm.models import Customer

    nombres = await svc.names(db, [i.technician_user_id for i, _ in filas])
    ids = {c.customer_id for _, c in filas if c and c.customer_id}
    clientes = dict((await db.execute(select(Customer.id, Customer.legal_name).where(Customer.id.in_(ids)))).all()) \
        if ids else {}
    salida = []
    for i, case in filas:
        salida.append(ElectricalInspectionResponse(
            id=i.id, case_id=i.case_id, case_number=case.case_number if case else None,
            address=", ".join(x for x in (case.address_street, case.address_unit, case.address_city) if x)
            if case else None,
            customer_name=clientes.get(case.customer_id) if case else None,
            technician_user_id=i.technician_user_id, technician_name=nombres.get(i.technician_user_id),
            scheduled_date=i.scheduled_date, status=i.status, status_label=svc.STATUS.get(i.status, i.status),
            notes=i.notes, panel_amperage=i.panel_amperage, viability=i.viability,
            viability_label=svc.VIABILITY.get(i.viability) if i.viability else None, tons=i.tons,
            water_heater_eligible=i.water_heater_eligible, induction_eligible=i.induction_eligible,
            result_notes=i.result_notes, completed_at=i.completed_at, cancel_reason=i.cancel_reason))
    return salida


async def _one(db, organization_id, ins) -> ElectricalInspectionResponse:
    case = await svc._case(db, organization_id, ins.case_id)
    return (await _out(db, [(ins, case)]))[0]


@router.get("/cases/{case_id}/electrical-inspections", response_model=list[ElectricalInspectionResponse])
async def list_case_electrical_inspections(
    case_id: uuid.UUID,
    response: Response,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("dispatch.manage", "cases.review", "cases.read_all")),
):
    case = await svc._case(db, organization_id, case_id)
    filas = await svc.list_for_case(db, organization_id=organization_id, case_id=case_id)
    limit, offset = pagination
    return await _out(db, [(i, case) for i in paginate_list(filas, limit=limit, offset=offset, response=response)])


@router.post("/cases/{case_id}/electrical-inspections", response_model=ElectricalInspectionResponse,
             status_code=201)
async def schedule_electrical_inspection(
    case_id: uuid.UUID,
    payload: ElectricalInspectionCreate,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    ins = await svc.schedule(db, organization_id=organization_id, user=current_user, case_id=case_id,
                             technician_id=payload.technician_user_id, scheduled_date=payload.scheduled_date,
                             notes=payload.notes)
    return await _one(db, organization_id, ins)


@router.get("/electrical-inspections", response_model=list[ElectricalInspectionResponse])
async def list_electrical_inspections(
    response: Response,
    status: str | None = None,
    pagination: tuple[int, int] = Depends(pagination_params),
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(_ver),
):
    limit, offset = pagination
    stmt = svc.inspections_stmt(organization_id=organization_id, user=current_user, status=status)
    return await _out(db, await paginate(db, stmt, limit=limit, offset=offset, response=response, scalars=False))


@router.get("/electrical-inspections/{inspection_id}", response_model=ElectricalInspectionResponse)
async def get_electrical_inspection(
    inspection_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(_ver),
):
    ins = await svc.get_inspection(db, organization_id=organization_id, inspection_id=inspection_id)
    svc.ensure_can_see(ins, current_user)
    return await _one(db, organization_id, ins)


@router.post("/electrical-inspections/{inspection_id}/result", response_model=ElectricalInspectionResponse)
async def record_electrical_inspection_result(
    inspection_id: uuid.UUID,
    payload: ElectricalInspectionResult,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_any_permission("checklists.complete", "dispatch.manage")),
):
    ins = await svc.record_result(db, organization_id=organization_id, user=current_user,
                                  inspection_id=inspection_id, data=payload.model_dump())
    return await _one(db, organization_id, ins)


@router.post("/electrical-inspections/{inspection_id}/cancel", response_model=ElectricalInspectionResponse)
async def cancel_electrical_inspection(
    inspection_id: uuid.UUID,
    payload: ElectricalInspectionCancel,
    db: AsyncSession = Depends(get_db),
    organization_id: uuid.UUID = Depends(get_organization_id),
    current_user: User = Depends(require_permission("dispatch.manage")),
):
    ins = await svc.cancel(db, organization_id=organization_id, user=current_user, inspection_id=inspection_id,
                           reason=payload.reason)
    return await _one(db, organization_id, ins)
