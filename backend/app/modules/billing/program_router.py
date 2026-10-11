"""Rutas de la configuración de cobro por programa (spec D6.2).

Leer: quien ve facturas (`invoices.read`). Cambiar: `billing.configure`
(Administrador y Contabilidad).
"""
import uuid
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.modules.billing import program_config
from app.modules.billing.requirements import AUTO_RULES
from app.modules.billing.schemas import Money
from app.modules.users.models import User
from app.shared.pagination import paginate_list, pagination_params

router = APIRouter(prefix="/billing/programs", tags=["billing-config"])


class ProgramSummary(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    active: bool
    model_config = {"from_attributes": True}


class ProfileResponse(BaseModel):
    program_id: uuid.UUID
    issuer_name: str | None
    issuer_address: str | None
    issuer_phone: str | None
    issuer_email: str | None
    legal_text: str | None
    expected_payment_days: int
    model_config = {"from_attributes": True}


class ProfileUpdate(BaseModel):
    issuer_name: str | None = Field(default=None, max_length=255)
    issuer_address: str | None = Field(default=None, max_length=500)
    issuer_phone: str | None = Field(default=None, max_length=50)
    issuer_email: str | None = Field(default=None, max_length=255)
    legal_text: str | None = None
    expected_payment_days: int | None = None


class RateCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    valid_from: date
    valid_to: date | None = None
    notes: str | None = None


class RateClose(BaseModel):
    valid_to: date


class RateResponse(BaseModel):
    id: uuid.UUID
    amount: Money
    valid_from: date
    valid_to: date | None
    notes: str | None
    model_config = {"from_attributes": True}


class JurisdictionCreate(BaseModel):
    kind: str
    value: str = Field(min_length=1, max_length=120)
    valid_from: date
    valid_to: date | None = None


class JurisdictionResponse(BaseModel):
    id: uuid.UUID
    kind: str
    value: str
    label: str
    valid_from: date
    valid_to: date | None
    model_config = {"from_attributes": True}


class RequirementCreate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    auto_code: str | None = None


class RequirementUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    active: bool | None = None
    sort_order: int | None = None


class RequirementResponse(BaseModel):
    id: uuid.UUID
    code: str
    label: str
    kind: str
    sort_order: int
    active: bool
    model_config = {"from_attributes": True}


_read = require_permission("invoices.read")
_configure = require_permission("billing.configure")


@router.get("", response_model=list[ProgramSummary])
async def list_programs(response: Response, pagination: tuple[int, int] = Depends(pagination_params),
                        db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_read)):
    limit, offset = pagination
    return paginate_list(await program_config.list_programs(db, organization_id=organization_id),
                         limit=limit, offset=offset, response=response)


@router.get("/auto-rules")
async def auto_rules(current_user: User = Depends(_read)) -> dict[str, str]:
    """Las reglas automáticas disponibles para armar el checklist."""
    return AUTO_RULES


@router.get("/{program_id}/profile", response_model=ProfileResponse)
async def get_profile(program_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    perfil = await program_config.ensure_profile(db, organization_id=organization_id, program_id=program_id)
    await db.commit()
    return perfil


@router.put("/{program_id}/profile", response_model=ProfileResponse)
async def update_profile(program_id: uuid.UUID, payload: ProfileUpdate, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_configure)):
    return await program_config.update_profile(db, organization_id=organization_id, user=current_user,
                                               program_id=program_id, changes=payload.model_dump(exclude_unset=True))


@router.get("/{program_id}/rates", response_model=list[RateResponse])
async def list_rates(program_id: uuid.UUID, response: Response, pagination: tuple[int, int] = Depends(pagination_params),
                     db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_read)):
    limit, offset = pagination
    return paginate_list(await program_config.list_rates(db, organization_id=organization_id, program_id=program_id),
                         limit=limit, offset=offset, response=response)


@router.post("/{program_id}/rates", response_model=RateResponse, status_code=201)
async def add_rate(program_id: uuid.UUID, payload: RateCreate, db: AsyncSession = Depends(get_db),
                   organization_id: uuid.UUID = Depends(get_organization_id),
                   current_user: User = Depends(_configure)):
    return await program_config.add_rate(db, organization_id=organization_id, user=current_user,
                                         program_id=program_id, **payload.model_dump())


@router.patch("/rates/{rate_id}/close", response_model=RateResponse)
async def close_rate(rate_id: uuid.UUID, payload: RateClose, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id),
                     current_user: User = Depends(_configure)):
    return await program_config.close_rate(db, organization_id=organization_id, user=current_user,
                                           rate_id=rate_id, valid_to=payload.valid_to)


@router.get("/{program_id}/jurisdictions", response_model=list[JurisdictionResponse])
async def list_jurisdictions(program_id: uuid.UUID, response: Response,
                             pagination: tuple[int, int] = Depends(pagination_params), db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(_read)):
    limit, offset = pagination
    return paginate_list(await program_config.list_jurisdictions(db, organization_id=organization_id,
                                                                program_id=program_id),
                         limit=limit, offset=offset, response=response)


@router.post("/{program_id}/jurisdictions", response_model=JurisdictionResponse, status_code=201)
async def add_jurisdiction(program_id: uuid.UUID, payload: JurisdictionCreate, db: AsyncSession = Depends(get_db),
                           organization_id: uuid.UUID = Depends(get_organization_id),
                           current_user: User = Depends(_configure)):
    return await program_config.add_jurisdiction(db, organization_id=organization_id, user=current_user,
                                                 program_id=program_id, **payload.model_dump())


@router.delete("/jurisdictions/{jurisdiction_id}", status_code=204)
async def delete_jurisdiction(jurisdiction_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                              organization_id: uuid.UUID = Depends(get_organization_id),
                              current_user: User = Depends(_configure)):
    await program_config.delete_jurisdiction(db, organization_id=organization_id, user=current_user,
                                             jurisdiction_id=jurisdiction_id)
    return Response(status_code=204)


@router.get("/{program_id}/requirements", response_model=list[RequirementResponse])
async def list_requirements(program_id: uuid.UUID, response: Response,
                            pagination: tuple[int, int] = Depends(pagination_params), db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_read)):
    reqs = await program_config.list_requirements(db, organization_id=organization_id, program_id=program_id)
    await db.commit()
    limit, offset = pagination
    return paginate_list(reqs, limit=limit, offset=offset, response=response)


@router.post("/{program_id}/requirements", response_model=RequirementResponse, status_code=201)
async def add_requirement(program_id: uuid.UUID, payload: RequirementCreate, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_configure)):
    return await program_config.add_requirement(db, organization_id=organization_id, user=current_user,
                                                program_id=program_id, label=payload.label or "",
                                                auto_code=payload.auto_code)


@router.patch("/requirements/{requirement_id}", response_model=RequirementResponse)
async def update_requirement(requirement_id: uuid.UUID, payload: RequirementUpdate,
                             db: AsyncSession = Depends(get_db),
                             organization_id: uuid.UUID = Depends(get_organization_id),
                             current_user: User = Depends(_configure)):
    return await program_config.update_requirement(db, organization_id=organization_id, user=current_user,
                                                   requirement_id=requirement_id,
                                                   changes=payload.model_dump(exclude_unset=True))
