import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.crm.models import ActivityType, CustomerStatus, CustomerType, LeadStatus, QuoteStatus


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


# --- Lead ----------------------------------------------------------------

class LeadCreate(AddressSchema):
    full_name: str = Field(min_length=1, max_length=255)
    company_name: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    benefit_type: str | None = None
    funder_program: str | None = None
    interested_service: str | None = None
    assigned_owner_user_id: uuid.UUID | None = None
    notes: str | None = None


class LeadUpdate(BaseModel):
    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    source: str | None = None
    benefit_type: str | None = None
    funder_program: str | None = None
    status: LeadStatus | None = None
    assigned_owner_user_id: uuid.UUID | None = None
    notes: str | None = None


class LeadResponse(AddressSchema):
    id: uuid.UUID
    full_name: str
    company_name: str | None
    phone: str | None
    email: str | None
    source: str | None
    benefit_type: str | None
    funder_program: str | None
    interested_service: str | None
    assigned_owner_user_id: uuid.UUID | None
    status: LeadStatus
    notes: str | None
    converted_customer_id: uuid.UUID | None
    converted_opportunity_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class LeadDuplicateWarning(BaseModel):
    lead_id: uuid.UUID
    full_name: str
    matched_on: list[str]


class LeadCreateResult(BaseModel):
    lead: LeadResponse
    possible_duplicates: list[LeadDuplicateWarning] = []


class LeadConvertRequest(BaseModel):
    opportunity_title: str | None = None
    opportunity_stage_code: str = "new"


class LeadConvertResponse(BaseModel):
    customer_id: uuid.UUID
    contact_id: uuid.UUID
    opportunity_id: uuid.UUID


# --- Pipeline stages / Opportunities ---------------------------------------

class PipelineStageResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    is_won: bool
    is_lost: bool
    model_config = {"from_attributes": True}


class FunderStatusResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    sort_order: int
    model_config = {"from_attributes": True}


class OpportunityCreate(AddressSchema):
    customer_id: uuid.UUID
    primary_contact_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    estimated_amount: float | None = None
    currency: str = "USD"
    probability: int | None = None
    expected_close_date: date | None = None
    stage_code: str = "new"
    owner_user_id: uuid.UUID | None = None
    benefit_type: str | None = None
    funder_program: str | None = None
    application_number: str | None = None
    approval_code: str | None = None
    funder_status_code: str | None = None
    utility_account_number: str | None = None
    meter_number: str | None = None
    unit_type: str | None = None
    scheduled_install_date: date | None = None


class OpportunityUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    estimated_amount: float | None = None
    probability: int | None = None
    expected_close_date: date | None = None
    owner_user_id: uuid.UUID | None = None
    benefit_type: str | None = None
    funder_program: str | None = None
    application_number: str | None = None
    approval_code: str | None = None
    funder_status_code: str | None = None
    utility_account_number: str | None = None
    meter_number: str | None = None
    unit_type: str | None = None
    scheduled_install_date: date | None = None
    loss_reason: str | None = None


class OpportunityStageChange(BaseModel):
    stage_code: str
    loss_reason: str | None = None


class OpportunityResponse(AddressSchema):
    id: uuid.UUID
    customer_id: uuid.UUID
    primary_contact_id: uuid.UUID | None
    title: str
    description: str | None
    estimated_amount: float | None
    currency: str
    probability: int | None
    expected_close_date: date | None
    stage: PipelineStageResponse
    owner_user_id: uuid.UUID | None
    loss_reason: str | None
    benefit_type: str | None
    funder_program: str | None
    application_number: str | None
    approval_code: str | None
    funder_status: FunderStatusResponse | None
    utility_account_number: str | None
    meter_number: str | None
    unit_type: str | None
    scheduled_install_date: date | None
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Activities ---------------------------------------------------------

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

class QuoteLineItemCreate(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    quantity: float = 1
    unit_price: float = 0
    discount: float = 0
    tax_value: float = 0


class QuoteLineItemResponse(QuoteLineItemCreate):
    id: uuid.UUID
    line_total: float
    model_config = {"from_attributes": True}


class QuoteCreate(BaseModel):
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None = None
    project_description: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    currency: str = "USD"
    notes: str | None = None
    line_items: list[QuoteLineItemCreate] = []


class QuoteResponse(BaseModel):
    id: uuid.UUID
    quote_number: str
    customer_id: uuid.UUID
    opportunity_id: uuid.UUID | None
    project_description: str | None
    issue_date: date | None
    expiry_date: date | None
    currency: str
    status: QuoteStatus
    notes: str | None
    total_amount: float
    line_items: list[QuoteLineItemResponse]
    model_config = {"from_attributes": True}


# --- Customer 360 -----------------------------------------------------------

class Customer360Response(BaseModel):
    customer: CustomerResponse
    opportunities: list[OpportunityResponse]
    activities: list[ActivityResponse]
    quotes: list[QuoteResponse]


# --- CSV import -----------------------------------------------------------

class ImportSummary(BaseModel):
    total_rows: int
    created: int
    skipped_duplicates: int
    errors: list[str] = []
