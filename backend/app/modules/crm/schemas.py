import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.cases.schemas import CaseResponse
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


# --- Aviso de tratamiento de datos personales -------------------------------

class DataConsentNotice(BaseModel):
    """El aviso que se muestra —y se guarda como constancia— al capturar datos
    personales del cliente. Lo entrega el servidor para que las cuatro
    pantallas que lo piden muestren el mismo texto y la misma versión."""

    version: str
    language: str
    title: str
    label: str
    body: str


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
    # El cliente autorizó el tratamiento de sus datos (obligatorio: sin esto no
    # se guarda nada personal). No es una columna del cliente.
    data_consent_accepted: bool = False


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
    data_consent_accepted: bool = False


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

