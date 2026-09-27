import uuid
from datetime import date, datetime

from app.modules.cases.schemas import CaseResponse
from pydantic import BaseModel, Field

from app.modules.crm.models import ActivityType, CustomerStatus, CustomerType


# --- Address (shared) -------------------------------------------------------

class AddressSchema(BaseModel):
    address_street: str | None = None
    address_unit: str | None = None
    address_city: str | None = None
    address_state: str | None = None
    address_zip: str | None = None
    latitude: float | None = None
    longitude: float | None = None


# --- Customer ----------------------------------------------------------------

class CustomerContactBase(BaseModel):
    full_name: str
    role_title: str | None = None
    email: str | None = None
    phone: str | None = None
    preferred_contact_method: str | None = None
    is_primary: bool = False


class CustomerContactCreate(CustomerContactBase):
    pass


class CustomerContactResponse(CustomerContactBase):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class CustomerCreate(BaseModel):
    legal_name: str = Field(min_length=1, max_length=255)
    customer_type: CustomerType = CustomerType.individual
    main_phone: str | None = None
    email: str | None = None
    website: str | None = None
    billing_address: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class CustomerUpdate(BaseModel):
    legal_name: str | None = None
    customer_type: CustomerType | None = None
    main_phone: str | None = None
    email: str | None = None
    website: str | None = None
    billing_address: str | None = None
    status: CustomerStatus | None = None
    tags: list[str] | None = None
    notes: str | None = None


class CustomerResponse(BaseModel):
    id: uuid.UUID
    legal_name: str
    customer_type: CustomerType
    main_phone: str | None
    email: str | None
    website: str | None
    billing_address: str | None
    status: CustomerStatus
    tags: list[str] | None
    notes: str | None
    contacts: list[CustomerContactResponse] = []
    model_config = {"from_attributes": True}


class ApplicationCreate(BaseModel):
    customer_id: uuid.UUID | None = None
    program_code: str = Field(min_length=1, max_length=100)
    form_version: str = "1"
    answers: dict = {}
    terms_version: str | None = None
    terms_accepted: bool = False


class ApplicationUpdate(BaseModel):
    answers: dict | None = None
    terms_version: str | None = None
    terms_accepted: bool | None = None
    status: str | None = None
    review_notes: str | None = None


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID | None
    program_code: str
    form_version: str
    status: str
    answers: dict
    terms_version: str | None
    terms_accepted: bool
    terms_accepted_at: datetime | None
    customer_signature_path: str | None
    customer_signed_at: datetime | None
    salesperson_user_id: uuid.UUID | None
    salesperson_signed_at: datetime | None
    review_notes: str | None
    reviewed_by_user_id: uuid.UUID | None
    reviewed_at: datetime | None
    submitted_at: datetime | None
    created_at: datetime
    model_config = {"from_attributes": True}


class ProgramFormFieldResponse(BaseModel):
    id: uuid.UUID
    program_code: str
    form_version: str
    field_key: str
    label: str
    field_type: str
    required: bool
    options: list | None
    sort_order: int
    active: bool
    model_config = {"from_attributes": True}


class ApplicationDocumentResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    field_key: str
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    uploaded_by_user_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


class ApplicationCustomerSignature(BaseModel):
    customer_name: str = Field(min_length=1, max_length=255)
    signature_base64: str = Field(min_length=10)


# --- Lead ----------------------------------------------------------------

class FunderStatusResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    model_config = {"from_attributes": True}


class ActivityCreate(BaseModel):
    type: ActivityType
    subject: str = Field(min_length=1, max_length=255)
    notes: str | None = None
    owner_user_id: uuid.UUID
    due_date: datetime | None = None
    reminder_at: datetime | None = None
    customer_id: uuid.UUID | None = None
    opportunity_id: uuid.UUID | None = None


class ActivityUpdate(BaseModel):
    subject: str | None = None
    notes: str | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None


class ActivityResponse(BaseModel):
    id: uuid.UUID
    type: ActivityType
    subject: str
    notes: str | None
    owner_user_id: uuid.UUID
    due_date: datetime | None
    completed_at: datetime | None
    reminder_at: datetime | None
    customer_id: uuid.UUID | None
    opportunity_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Quotes ---------------------------------------------------------------

class Customer360Response(BaseModel):
    """Ficha del cliente: sus expedientes y su actividad.

    `opportunities` y `quotes` se retiraron con el modelo anterior."""

    customer: CustomerResponse
    cases: list[CaseResponse]
    activities: list[ActivityResponse]


# --- CSV import -----------------------------------------------------------

