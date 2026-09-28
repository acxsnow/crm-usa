import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.modules.crm.schemas import AddressSchema
from app.modules.field_ops.models import ProjectStatus, TaskStatus


# --- Technician monitor -------------------------------------------------

class TechnicianMonitorRow(BaseModel):
    user_id: uuid.UUID
    full_name: str
    logueado: bool
    en_cola: bool
    casos_asignados: int
    casos_gestionados_hoy: int
    tiempo_gestion_hoy_dias: float | None


class AvailabilityUpdate(BaseModel):
    is_available: bool


# --- Projects ----------------------------------------------------------

class ProjectCreate(AddressSchema):
    customer_id: uuid.UUID
    # El expediente del que nace el proyecto; reemplazó a `opportunity_id`.
    case_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    project_type: str | None = None
    scheduled_date: date | None = None
    primary_technician_user_id: uuid.UUID | None = None
    notes: str | None = None
    apply_checklist_template_id: uuid.UUID | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    status: ProjectStatus | None = None
    scheduled_date: date | None = None
    completed_date: date | None = None
    primary_technician_user_id: uuid.UUID | None = None
    notes: str | None = None


class ProjectResponse(AddressSchema):
    id: uuid.UUID
    customer_id: uuid.UUID
    case_id: uuid.UUID | None
    title: str
    project_type: str | None
    status: ProjectStatus
    scheduled_date: date | None
    completed_date: date | None
    primary_technician_user_id: uuid.UUID | None
    notes: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Checklists ----------------------------------------------------------

class ChecklistTemplateItemCreate(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    sort_order: int = 0
    is_required: bool = True
    requires_evidence: bool = False


class ChecklistTemplateItemResponse(ChecklistTemplateItemCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class ChecklistTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_type: str | None = None
    items: list[ChecklistTemplateItemCreate] = []


class ChecklistTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    project_type: str | None
    items: list[ChecklistTemplateItemResponse]
    model_config = {"from_attributes": True}


class ProjectChecklistItemResponse(BaseModel):
    id: uuid.UUID
    label: str
    sort_order: int
    is_required: bool
    requires_evidence: bool
    is_complete: bool
    completed_at: datetime | None
    completed_by_user_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class ChecklistItemComplete(BaseModel):
    is_complete: bool = True


# --- Tasks ---------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    assigned_user_id: uuid.UUID | None = None
    due_date: datetime | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    assigned_user_id: uuid.UUID | None = None
    due_date: datetime | None = None
    completed_at: datetime | None = None


class TaskResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    status: TaskStatus
    assigned_user_id: uuid.UUID | None
    due_date: datetime | None
    completed_at: datetime | None
    is_overdue: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class OverdueTaskResponse(TaskResponse):
    project_title: str


class TaskCommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


class TaskCommentResponse(BaseModel):
    id: uuid.UUID
    task_id: uuid.UUID
    author_user_id: uuid.UUID
    body: str
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Evidence --------------------------------------------------------------

class EvidenceResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    task_id: uuid.UUID | None
    checklist_item_id: uuid.UUID | None
    category: str
    original_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    latitude: float | None
    longitude: float | None
    captured_at: datetime | None
    watermarked: bool
    uploaded_by_user_id: uuid.UUID
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Attestation -----------------------------------------------------------

class SignatureCapture(BaseModel):
    signature_base64: str = Field(min_length=10, description="PNG signature, data URL or bare base64")


class CustomerSignatureCapture(SignatureCapture):
    customer_name: str = Field(min_length=1, max_length=255)


class AttestationResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    technician_user_id: uuid.UUID | None
    technician_signed_at: datetime | None
    customer_name: str | None
    customer_signed_at: datetime | None
    pdf_path: str | None
    generated_at: datetime | None
    is_fully_signed: bool
    model_config = {"from_attributes": True}


class CustomerSignatureRequestResponse(BaseModel):
    status: str
    recipient_email: str
    expires_at: datetime


class PublicSignatureResponse(BaseModel):
    project_title: str
    customer_name: str | None
    expires_at: datetime
    technician_signed: bool


class PublicCustomerSignatureCapture(CustomerSignatureCapture):
    pass
