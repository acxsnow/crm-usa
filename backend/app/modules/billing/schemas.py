import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer

# Dinero: `Decimal` adentro, número en el JSON. Pydantic serializa Decimal como
# texto por defecto y el frontend espera números; el valor ya viene redondeado a
# centavos, así que convertirlo al serializar no pierde nada.
Money = Annotated[Decimal, PlainSerializer(lambda v: float(v), return_type=float, when_used="json")]


class InvoiceLineIn(BaseModel):
    kind: str = "service"
    description: str = Field(min_length=1, max_length=500)
    service_code: str | None = Field(default=None, max_length=50)
    quantity: Decimal = Field(default=Decimal("1"), gt=0)
    unit_price: Decimal = Field(ge=0)


class InvoiceLineResponse(BaseModel):
    id: uuid.UUID
    kind: str
    description: str
    service_code: str | None
    quantity: Money
    unit_price: Money
    amount: Money
    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    """Factura particular. Con líneas, o solo con `amount` como antes del
    módulo 6 (se guarda como una línea de servicio)."""
    project_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    lines: list[InvoiceLineIn] = []
    funder_program: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    """Solo datos que no cambian lo facturado: una factura emitida no se edita
    (se anula y se emite otra)."""
    due_date: date | None = None
    notes: str | None = None


class InvoiceLinesReplace(BaseModel):
    """Solo para borradores (la factura que sale de una cotización)."""
    lines: list[InvoiceLineIn] = Field(min_length=1)


class InvoiceIssue(BaseModel):
    due_date: date | None = None


class InvoiceVoid(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)


class InvoicePaymentCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    paid_at: date
    method: str | None = None
    reference: str | None = None
    notes: str | None = None


class InvoicePaymentResponse(BaseModel):
    id: uuid.UUID
    amount: Money
    paid_at: date
    method: str | None
    reference: str | None
    notes: str | None
    model_config = {"from_attributes": True}


class InvoiceAttachmentResponse(BaseModel):
    id: uuid.UUID
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    created_at: datetime
    model_config = {"from_attributes": True}


class InvoicePreview(BaseModel):
    """Lo que se emitiría, para verlo en PDF antes (no guarda ni numera).
    Rebate: `project_id` + `program_id`. Particular: `lines` y cliente o
    proyecto."""
    kind: str = "particular"
    project_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None
    customer_id: uuid.UUID | None = None
    lines: list[InvoiceLineIn] = []
    due_date: date | None = None
    notes: str | None = None


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    kind: str
    project_id: uuid.UUID | None
    case_id: uuid.UUID | None
    customer_id: uuid.UUID
    replaces_invoice_id: uuid.UUID | None
    claim_id: uuid.UUID | None = None
    quote_id: uuid.UUID | None = None
    invoice_number: str
    funder_program: str | None
    # Lo cobrable (ver `Invoice`), lo pagado y lo que falta.
    amount: Money
    paid_amount: Money
    balance: Money
    subtotal: Money
    rebate_total: Money
    customer_total: Money
    document_status: str
    # Estado de pago a la fecha de la organización: unpaid, partial, paid,
    # overdue; o draft/void si el documento no está emitido.
    status: str
    issue_date: date | None
    due_date: date | None
    sent_at: datetime | None
    paid_at: datetime | None
    void_reason: str | None
    notes: str | None
    lines: list[InvoiceLineResponse]
    payments: list[InvoicePaymentResponse]
    attachments: list[InvoiceAttachmentResponse]
    created_at: datetime


class FinanceDashboardResponse(BaseModel):
    total_invoiced: Money
    total_paid: Money
    total_outstanding: Money
    total_overdue: Money
    invoice_count: int
    overdue_count: int
    due_soon_count: int  # vencen en los próximos 7 días y no están pagadas
    # Pagos registrados este mes (programas y particulares), para el Inicio.
    paid_this_month: Money


def invoice_response(invoice, today: date) -> InvoiceResponse:
    """El estado de pago depende del día de la organización, así que la
    respuesta se arma con ese día y no con un validador automático."""
    datos = {campo: getattr(invoice, campo) for campo in InvoiceResponse.model_fields if campo != "status"}
    return InvoiceResponse.model_validate({**datos, "status": invoice.payment_status_on(today)}, from_attributes=True)
