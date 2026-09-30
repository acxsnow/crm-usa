"""Rutas de cotizaciones de trabajo particular (spec D6.7). Todo con
`quotes.manage` (Administrador, Administración y Contabilidad).

Bajo `/billing/quotes`, no `/quotes`: esa ruta era del CRM anterior que la
Cadena A retiró (COD-01) y su prueba exige que no responda."""
import uuid
from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_organization_id, require_permission
from app.db.session import get_db
from app.modules.billing import quotes as quotes_service
from app.modules.billing.models import QUOTE_STATUS_LABELS
from app.modules.billing.schemas import InvoiceLineIn, InvoiceLineResponse, InvoiceResponse, Money, invoice_response
from app.modules.users.models import User

router = APIRouter(prefix="/billing/quotes", tags=["quotes"])


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    title: str | None = Field(default=None, max_length=255)
    valid_until: date | None = None
    notes: str | None = None
    lines: list[InvoiceLineIn] = Field(min_length=1)


class QuoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    valid_until: date | None = None
    notes: str | None = None
    lines: list[InvoiceLineIn] | None = None


class QuoteReject(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class QuoteVersion(BaseModel):
    id: uuid.UUID
    version: int
    status: str
    total: Money
    created_at: datetime


class QuoteResponse(BaseModel):
    id: uuid.UUID
    quote_number: str
    version: int
    previous_version_id: uuid.UUID | None
    customer_id: uuid.UUID
    project_id: uuid.UUID | None
    status: str  # incluye "expired", calculado a la fecha de la organización
    status_label: str
    title: str | None
    valid_until: date | None
    notes: str | None
    sent_at: datetime | None
    decided_at: datetime | None
    rejection_reason: str | None
    total: Money
    lines: list[InvoiceLineResponse]
    created_at: datetime


class QuoteDetailResponse(QuoteResponse):
    versions: list[QuoteVersion]
    invoice: InvoiceResponse | None


class QuoteAcceptResponse(BaseModel):
    quote: QuoteResponse
    invoice: InvoiceResponse


def _quote(q, hoy: date) -> dict:
    estado = q.status_on(hoy)
    return {
        **{c: getattr(q, c) for c in (
            "id", "quote_number", "version", "previous_version_id", "customer_id", "project_id", "title",
            "valid_until", "notes", "sent_at", "decided_at", "rejection_reason", "total", "created_at",
        )},
        "status": estado, "status_label": QUOTE_STATUS_LABELS[estado],
        "lines": [InvoiceLineResponse.model_validate(l) for l in q.lines],
    }


async def _detail(db, q) -> QuoteDetailResponse:
    from app.modules.field_ops.clock import org_today

    hoy = await org_today(db, q.organization_id)
    factura = await quotes_service.invoice_of(db, q)
    return QuoteDetailResponse.model_validate({
        **_quote(q, hoy),
        "versions": [{"id": v.id, "version": v.version, "status": v.status_on(hoy), "total": v.total,
                      "created_at": v.created_at} for v in await quotes_service.versions_of(db, q)],
        "invoice": invoice_response(factura, hoy) if factura else None,
    })


_manage = require_permission("quotes.manage")


@router.get("", response_model=list[QuoteResponse])
async def list_quotes(customer_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None,
                      status: str | None = Query(default=None), include_history: bool = False,
                      db: AsyncSession = Depends(get_db), organization_id: uuid.UUID = Depends(get_organization_id),
                      current_user: User = Depends(_manage)):
    quotes, hoy = await quotes_service.list_quotes(db, organization_id=organization_id, customer_id=customer_id,
                                                   project_id=project_id, status=status,
                                                   include_history=include_history)
    return [QuoteResponse.model_validate(_quote(q, hoy)) for q in quotes]


@router.post("", response_model=QuoteDetailResponse, status_code=201)
async def create_quote(payload: QuoteCreate, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    datos = payload.model_dump()
    q = await quotes_service.create_quote(db, organization_id=organization_id, user=current_user, data=datos)
    return await _detail(db, q)


@router.get("/{quote_id}", response_model=QuoteDetailResponse)
async def get_quote(quote_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                    organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_manage)):
    return await _detail(db, await quotes_service.get_quote_or_404(db, organization_id=organization_id,
                                                                   quote_id=quote_id))


@router.patch("/{quote_id}", response_model=QuoteDetailResponse)
async def update_quote(quote_id: uuid.UUID, payload: QuoteUpdate, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    q = await quotes_service.update_quote(db, organization_id=organization_id, user=current_user, quote_id=quote_id,
                                          changes=payload.model_dump(exclude_unset=True))
    return await _detail(db, q)


@router.post("/{quote_id}/send", response_model=QuoteDetailResponse)
async def send_quote(quote_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                     organization_id: uuid.UUID = Depends(get_organization_id), current_user: User = Depends(_manage)):
    return await _detail(db, await quotes_service.send_quote(db, organization_id=organization_id, user=current_user,
                                                             quote_id=quote_id))


@router.post("/{quote_id}/revise", response_model=QuoteDetailResponse, status_code=201)
async def revise_quote(quote_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    return await _detail(db, await quotes_service.revise_quote(db, organization_id=organization_id,
                                                               user=current_user, quote_id=quote_id))


@router.post("/{quote_id}/accept", response_model=QuoteAcceptResponse)
async def accept_quote(quote_id: uuid.UUID, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    from app.modules.field_ops.clock import org_today

    q, factura = await quotes_service.accept_quote(db, organization_id=organization_id, user=current_user,
                                                   quote_id=quote_id)
    hoy = await org_today(db, organization_id)
    return {"quote": QuoteResponse.model_validate(_quote(q, hoy)), "invoice": invoice_response(factura, hoy)}


@router.post("/{quote_id}/reject", response_model=QuoteDetailResponse)
async def reject_quote(quote_id: uuid.UUID, payload: QuoteReject, db: AsyncSession = Depends(get_db),
                       organization_id: uuid.UUID = Depends(get_organization_id),
                       current_user: User = Depends(_manage)):
    return await _detail(db, await quotes_service.reject_quote(db, organization_id=organization_id,
                                                               user=current_user, quote_id=quote_id,
                                                               reason=payload.reason))
