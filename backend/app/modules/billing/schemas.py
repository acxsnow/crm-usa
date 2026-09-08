import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.billing.models import InvoiceStatus


class InvoiceCreate(BaseModel):
    project_id: uuid.UUID
    amount: float = Field(gt=0)
    funder_program: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoiceUpdate(BaseModel):
    amount: float | None = None
    funder_program: str | None = None
    issue_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class InvoicePaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    paid_at: date
    method: str | None = None
    reference: str | None = None
    notes: str | None = None


class InvoicePaymentResponse(BaseModel):
    id: uuid.UUID
    amount: float
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


class InvoiceResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    customer_id: uuid.UUID
    invoice_number: str
    funder_program: str | None
    amount: float
    paid_amount: float
    balance: float
    status: InvoiceStatus
    issue_date: date | None
    due_date: date | None
    sent_at: datetime | None
    paid_at: datetime | None
    notes: str | None
    payments: list[InvoicePaymentResponse]
    attachments: list[InvoiceAttachmentResponse]
    created_at: datetime
    model_config = {"from_attributes": True}


class FinanceDashboardResponse(BaseModel):
    total_invoiced: float
    total_paid: float
    total_outstanding: float
    total_overdue: float
    invoice_count: int
    overdue_count: int
    due_soon_count: int  # due within 7 days, not yet paid
