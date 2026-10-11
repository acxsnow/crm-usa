"""Rutas del cobro de rebate (spec §7).

Permisos:
- Ver: `invoices.read` (Administración, Contabilidad, Gerencia).
- Crear, checklist, radicar, rechazar, retirar y refacturar: `billing.submit`
  (Administración y Contabilidad).
- Registrar el pago del programa: `invoices.record_payment` (Contabilidad).
"""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.modules.billing import claims as claims_service
from app.modules.billing.dashboard import project_context
from app.modules.billing.models import CLAIM_STATUS_LABELS
from app.modules.billing.schemas import InvoiceResponse, Money, invoice_response
from app.modules.field_ops.clock import org_today
from app.modules.users.models import User
from app.shared.pagination import paginate, pagination_params

router = APIRouter(tags=["billing-claims"])


# ---------------------------------------------------------------------------
# Esquemas
# ---------------------------------------------------------------------------

class EligibleProgram(BaseModel):
    program_id: uuid.UUID
    program_code: str
    program_name: str
    applies: bool
    jurisdiction_label: str | None
    rate: Money | None
    claim_id: uuid.UUID | None
    claim_status: str | None


class EligibilityResponse(BaseModel):
    project_id: uuid.UUID
    installation_date: date | None
    evaluated_on: date
    technician_info_confirmed: bool
    programs: list[EligibleProgram]


class ClaimCreate(BaseModel):
    program_id: uuid.UUID
    override_reason: str | None = Field(default=None, max_length=1000)


class CheckConfirm(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ClaimSubmit(BaseModel):
    portal_reference: str | None = Field(default=None, max_length=255)
    submitted_on: date | None = None


class ClaimReject(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)
    category: str
    return_to_technician: bool = False


class ClaimPayment(BaseModel):
    amount: Money = Field(gt=0)
    paid_on: date
    reference: str | None = Field(default=None, max_length=255)
    method: str | None = Field(default=None, max_length=100)


class ReasonIn(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class AttemptResponse(BaseModel):
    id: uuid.UUID
    submitted_on: date
    portal_reference: str | None
    submitted_by_user_id: uuid.UUID | None
    result: str
    rejection_category: str | None
    rejection_reason: str | None
    resolved_on: date | None
    model_config = {"from_attributes": True}


class RequirementStatus(BaseModel):
    code: str
    label: str
    kind: str
    met: bool
    detail: str | None
    confirmed_by_user_id: uuid.UUID | None
    confirmed_at: datetime | None
    note: str | None


class ClaimResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    case_id: uuid.UUID | None
    case_number: str | None = None
    customer_name: str | None = None
    address: str | None = None
    program_id: uuid.UUID
    program_code: str
    program_name: str
    status: str
    status_label: str
    amount: Money
    installation_date: date
    applies: bool
    jurisdiction_label: str | None
    override_reason: str | None
    paid_on: date | None
    paid_amount: Money | None
    difference: Money | None
    payment_reference: str | None
    withdrawn_reason: str | None
    invoice: InvoiceResponse | None
    attempts: list[AttemptResponse]
    created_at: datetime


class ClaimDetailResponse(ClaimResponse):
    requirements: list[RequirementStatus]
    ready_to_submit: bool


def _claim_response(claim, today: date, contexto: dict | None = None) -> dict:
    """`contexto`: cliente, dirección y expediente por proyecto (ver
    `dashboard.project_context`), para no consultar uno por uno."""
    datos = (contexto or {}).get(claim.project_id, {})
    return {
        "case_number": datos.get("case_number"),
        "customer_name": datos.get("customer_name"),
        "address": datos.get("address"),
        **{campo: getattr(claim, campo) for campo in (
            "id", "project_id", "case_id", "program_id", "status", "amount", "installation_date", "applies",
            "jurisdiction_label", "override_reason", "paid_on", "paid_amount", "difference", "payment_reference",
            "withdrawn_reason", "created_at",
        )},
        "program_code": claim.program.code,
        "program_name": claim.program.name,
        "status_label": CLAIM_STATUS_LABELS[claim.status],
        "invoice": invoice_response(claim.invoice, today) if claim.invoice else None,
        "attempts": [AttemptResponse.model_validate(a) for a in claim.attempts],
    }


async def _detail(db, claim) -> ClaimDetailResponse:
    hoy = await org_today(db, claim.organization_id)
    requisitos = await claims_service.claim_checklist(db, claim=claim)
    contexto = await project_context(db, claim.organization_id, {claim.project_id})
    return ClaimDetailResponse.model_validate({
        **_claim_response(claim, hoy, contexto),
        "requirements": requisitos,
        "ready_to_submit": all(r["met"] for r in requisitos),
    })


_read = require_permission("invoices.read")
_submit = require_permission("billing.submit")
_pay = require_permission("invoices.record_payment")


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

@router.get("/projects/{project_id}/billing/eligibility", response_model=EligibilityResponse)
async def eligibility(project_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_read)):
    return await claims_service.eligibility(db, organization_id=organization_id, user=current_user,
                                            project_id=project_id)


@router.post("/projects/{project_id}/claims", response_model=ClaimDetailResponse, status_code=201)
async def create_claim(project_id: uuid.UUID, payload: ClaimCreate, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_submit)):
    claim = await claims_service.create_claim(
        db, organization_id=organization_id, user=current_user, project_id=project_id,
        program_id=payload.program_id, override_reason=payload.override_reason,
    )
    return await _detail(db, claim)


@router.get("/claims", response_model=list[ClaimResponse])
async def list_claims(response: Response, status: str | None = Query(default=None), program_id: uuid.UUID | None = None,
                      project_id: uuid.UUID | None = None, db: AsyncSession = Depends(get_db),
                      organization_id: uuid.UUID = Depends(get_organization_id),
                      pagination: tuple[int, int] = Depends(pagination_params),
                      current_user: User = Depends(_read)):
    """Paginado (`limit`/`offset`, total en X-Total-Count): crece con cada instalación."""
    hoy = await org_today(db, organization_id)
    limit, offset = pagination
    cobros = await paginate(db, claims_service.claims_query(organization_id=organization_id, status=status,
                                                            program_id=program_id, project_id=project_id),
                            limit=limit, offset=offset, response=response)
    contexto = await project_context(db, organization_id, {c.project_id for c in cobros})
    return [ClaimResponse.model_validate(_claim_response(c, hoy, contexto)) for c in cobros]


@router.get("/claims/{claim_id}", response_model=ClaimDetailResponse)
async def get_claim(claim_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id),
                    current_user: User = Depends(_read)):
    claim = await claims_service.get_claim_or_404(db, organization_id=organization_id, claim_id=claim_id)
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/checks/{code}", response_model=ClaimDetailResponse)
async def confirm_check(claim_id: uuid.UUID, code: str, payload: CheckConfirm, db: AsyncSession = Depends(get_db),
                        organization_id: uuid.UUID = Depends(get_organization_id),
                        current_user: User = Depends(_submit)):
    claim = await claims_service.confirm_manual_check(db, organization_id=organization_id, user=current_user,
                                                      claim_id=claim_id, code=code, note=payload.note)
    return await _detail(db, claim)


@router.delete("/claims/{claim_id}/checks/{code}", response_model=ClaimDetailResponse)
async def remove_check(claim_id: uuid.UUID, code: str, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_submit)):
    claim = await claims_service.remove_manual_check(db, organization_id=organization_id, user=current_user,
                                                     claim_id=claim_id, code=code)
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/submit", response_model=ClaimDetailResponse)
async def submit_claim(claim_id: uuid.UUID, payload: ClaimSubmit, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_submit)):
    claim = await claims_service.submit_claim(db, organization_id=organization_id, user=current_user,
                                              claim_id=claim_id, portal_reference=payload.portal_reference,
                                              submitted_on=payload.submitted_on)
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/reject", response_model=ClaimDetailResponse)
async def reject_claim(claim_id: uuid.UUID, payload: ClaimReject, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_submit)):
    claim = await claims_service.reject_claim(db, organization_id=organization_id, user=current_user,
                                              claim_id=claim_id, reason=payload.reason, category=payload.category,
                                              return_to_technician=payload.return_to_technician)
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/payment", response_model=ClaimDetailResponse)
async def record_payment(claim_id: uuid.UUID, payload: ClaimPayment, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_pay)):
    claim = await claims_service.record_claim_payment(
        db, organization_id=organization_id, user=current_user, claim_id=claim_id, amount=payload.amount,
        paid_on=payload.paid_on, reference=payload.reference, method=payload.method,
    )
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/withdraw", response_model=ClaimDetailResponse)
async def withdraw_claim(claim_id: uuid.UUID, payload: ReasonIn, db: AsyncSession = Depends(get_db),
                         organization_id: uuid.UUID = Depends(get_organization_id),
                         current_user: User = Depends(_submit)):
    claim = await claims_service.withdraw_claim(db, organization_id=organization_id, user=current_user,
                                                claim_id=claim_id, reason=payload.reason)
    return await _detail(db, claim)


@router.post("/claims/{claim_id}/invoice/reissue", response_model=ClaimDetailResponse)
async def reissue_invoice(claim_id: uuid.UUID, payload: ReasonIn, db: AsyncSession = Depends(get_db),
                          organization_id: uuid.UUID = Depends(get_organization_id),
                          current_user: User = Depends(_submit)):
    claim = await claims_service.reissue_invoice(db, organization_id=organization_id, user=current_user,
                                                 claim_id=claim_id, reason=payload.reason)
    return await _detail(db, claim)


# ---------------------------------------------------------------------------
# Tablero de cobros (spec D6.10)
# ---------------------------------------------------------------------------

class DashboardProjectItem(BaseModel):
    project_id: uuid.UUID
    customer_name: str | None
    address: str | None
    case_id: uuid.UUID | None
    case_number: str | None
    days: int
    alert: bool


class DashboardToCreate(DashboardProjectItem):
    confirmed_on: date
    installation_date: date | None


class DashboardClaimItem(DashboardProjectItem):
    claim_id: uuid.UUID
    program_id: uuid.UUID
    program_code: str
    program_name: str
    amount: Money


class DashboardToSubmit(DashboardClaimItem):
    ready_to_submit: bool
    pending_requirements: int


class DashboardSubmitted(DashboardClaimItem):
    submitted_on: date
    expected_payment_days: int


class DashboardRejected(DashboardClaimItem):
    rejection_reason: str | None
    rejection_category: str | None


class DashboardPaid(DashboardClaimItem):
    paid_on: date
    paid_amount: Money
    difference: Money | None


class DashboardAging(BaseModel):
    d0_30: Money
    d31_45: Money
    d46_plus: Money
    open_total: Money


class DashboardProgram(BaseModel):
    program_id: uuid.UUID
    program_code: str
    program_name: str
    paid_this_month: Money
    expected: Money
    submitted_count: int


class DashboardParticular(BaseModel):
    overdue_count: int
    overdue_total: Money
    due_soon_count: int
    due_soon_total: Money
    outstanding_total: Money
    draft_count: int


class BillingDashboardResponse(BaseModel):
    today: date
    to_create: list[DashboardToCreate]
    to_submit: list[DashboardToSubmit]
    submitted: list[DashboardSubmitted]
    rejected: list[DashboardRejected]
    paid_this_month: list[DashboardPaid]
    aging: DashboardAging
    by_program: list[DashboardProgram]
    particular: DashboardParticular


@router.get("/billing/dashboard", response_model=BillingDashboardResponse)
async def billing_dashboard(db: AsyncSession = Depends(get_db),
                            organization_id: uuid.UUID = Depends(get_organization_id),
                            current_user: User = Depends(_read)):
    from app.modules.billing.dashboard import billing_dashboard as build

    return await build(db, organization_id=organization_id)
