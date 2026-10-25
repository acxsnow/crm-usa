import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.modules.crm.schemas import AddressSchema
from app.modules.field_ops.catalogs import EVIDENCE_CATEGORIES, INSTALLATION_CONDITIONS
from app.modules.field_ops.models import ProjectStatus, TaskStatus


def _check_code(value: str | None, catalog: dict[str, str], what: str) -> str | None:
    if value is not None and value not in catalog:
        raise ValueError(f"{what} «{value}» no existe.")
    return value


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
    """Solo datos descriptivos. Estado, fechas y técnico se cambian por sus
    comandos (agendar, cerrar instalación), que validan y mueven el expediente;
    antes este PATCH permitía marcar `completed` sin cierre (contrato §7)."""
    model_config = {"extra": "forbid"}

    title: str | None = Field(default=None, min_length=1, max_length=255)
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
    installation_conditions: list[str] = []
    equipment_confirmed_at: datetime | None = None
    case_number: str | None = None
    case_stage_code: str | None = None
    case_stage_label: str | None = None
    case_substatus_code: str | None = None
    # Revisión administrativa del acta (módulo 6).
    technician_info_confirmed: bool = False
    returned_reason: str | None = None
    # Para quien pide: «full» si llena la obra, «read_only» si la ve porque fue
    # su responsable antes o va de ayudante (plan bodega-cierre, fase 5).
    my_access: str = "full"
    # Visitas fallidas y cancelación (D-001).
    failed_visits_count: int = 0
    extra_visits_authorized: int = 0
    cancelled_at: datetime | None = None
    cancel_reason: str | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


class InstallationConditionsUpdate(BaseModel):
    conditions: list[str]


# --- Checklists ----------------------------------------------------------

class ChecklistTemplateItemCreate(BaseModel):
    label: str = Field(min_length=1, max_length=500)
    sort_order: int = 0
    is_required: bool = True
    requires_evidence: bool = False
    section: str | None = Field(default=None, max_length=120)
    evidence_category: str | None = None
    condition_code: str | None = None
    allows_not_applicable: bool = False

    @field_validator("evidence_category")
    @classmethod
    def _evidence_category(cls, v):
        return _check_code(v, EVIDENCE_CATEGORIES, "La categoría de evidencia")

    @field_validator("condition_code")
    @classmethod
    def _condition(cls, v):
        return _check_code(v, INSTALLATION_CONDITIONS, "La condición")


class ChecklistTemplateItemResponse(ChecklistTemplateItemCreate):
    id: uuid.UUID
    model_config = {"from_attributes": True}


class ChecklistTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_type: str | None = None
    program_id: uuid.UUID | None = None
    items: list[ChecklistTemplateItemCreate] = []


class ChecklistTemplateResponse(BaseModel):
    id: uuid.UUID
    name: str
    project_type: str | None
    program_id: uuid.UUID | None = None
    items: list[ChecklistTemplateItemResponse]
    model_config = {"from_attributes": True}


class ProjectChecklistItemResponse(BaseModel):
    id: uuid.UUID
    label: str
    sort_order: int
    is_required: bool
    requires_evidence: bool
    section: str | None
    evidence_category: str | None
    condition_code: str | None
    allows_not_applicable: bool
    is_complete: bool
    not_applicable: bool
    not_applicable_reason: str | None
    completed_at: datetime | None
    completed_by_user_id: uuid.UUID | None
    model_config = {"from_attributes": True}


class ChecklistItemUpdate(BaseModel):
    """`{"is_complete": true}` completa; `{"not_applicable": true, "reason": …}`
    marca "No aplica"; `{"is_complete": false}` devuelve a pendiente."""
    is_complete: bool | None = None
    not_applicable: bool | None = None
    reason: str | None = Field(default=None, max_length=1000)


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
    # Enlace de firma enviado al cliente y todavía usable, para que la pantalla
    # lo sepa después de recargar.
    customer_link_sent_to: str | None = None
    customer_link_expires_at: datetime | None = None
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
    # La página pública manda el token en el cuerpo (no queda en registros de
    # URL); se sigue aceptando en la URL por compatibilidad.
    token: str | None = Field(default=None, max_length=200)


# --- Módulo 5: permisos municipales ---------------------------------------

class PermitCreate(BaseModel):
    jurisdiction: str = Field(min_length=1, max_length=150)
    permit_number: str | None = Field(default=None, max_length=100)
    permit_type: str | None = Field(default=None, max_length=100)
    status: str = "submitted"
    filed_on: date | None = None
    approved_on: date | None = None
    expires_on: date | None = None
    not_required_reason: str | None = None
    notes: str | None = None


class PermitUpdate(BaseModel):
    jurisdiction: str | None = Field(default=None, min_length=1, max_length=150)
    permit_number: str | None = Field(default=None, max_length=100)
    permit_type: str | None = Field(default=None, max_length=100)
    status: str | None = None
    filed_on: date | None = None
    approved_on: date | None = None
    expires_on: date | None = None
    not_required_reason: str | None = None
    notes: str | None = None


class PermitResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    jurisdiction: str
    permit_number: str | None
    permit_type: str | None
    status: str
    filed_on: date | None
    approved_on: date | None
    expires_on: date | None
    not_required_reason: str | None
    notes: str | None
    is_expired: bool
    is_cleared: bool
    # Si deja pasar a «Listo para instalar» (incluye radicado con PERMIT_FILED_ALLOWS_INSTALL).
    allows_install: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# --- Módulo 5: equipos, materiales, agenda y cierre ------------------------

class EquipmentCreate(BaseModel):
    equipment_type: str
    brand: str = Field(min_length=1, max_length=100)
    model: str = Field(min_length=1, max_length=100)
    serial_number: str | None = Field(default=None, max_length=100)
    quantity: int = Field(default=1, ge=1, le=50)
    unit_label: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    # El serial que salió de bodega para la obra (D-007), elegido de
    # `GET /projects/{id}/serials`. Sin él, el serial escrito se cruza solo.
    warehouse_serial_id: uuid.UUID | None = None


class EquipmentResponse(EquipmentCreate):
    id: uuid.UUID
    project_id: uuid.UUID
    recorded_by_user_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}


class MaterialCreate(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=100)
    quantity: float = Field(gt=0, le=100000)
    unit: str | None = Field(default=None, max_length=30)
    notes: str | None = None


class MaterialResponse(MaterialCreate):
    id: uuid.UUID
    project_id: uuid.UUID
    created_at: datetime
    # La línea de la orden de salida de bodega que lo entregó, cuando vino de
    # allí: es lo que deja marcado en el acta de dónde salió cada cosa.
    warehouse_release_line_id: uuid.UUID | None = None
    model_config = {"from_attributes": True}


class ScheduleInstallationRequest(BaseModel):
    technician_user_id: uuid.UUID
    scheduled_date: date


class CloseInstallationRequest(BaseModel):
    observations: str | None = Field(default=None, max_length=2000)


class FailedVisitRequest(BaseModel):
    reason_code: str = Field(max_length=40)
    notes: str = Field(max_length=2000)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ReasonRequest(BaseModel):
    reason: str = Field(max_length=2000)


class CancelProjectRequest(BaseModel):
    reason: str = Field(max_length=2000)
    # Qué pasó con el material entregado que no volvió a bodega.
    material_note: str | None = Field(default=None, max_length=2000)


class FieldOpsSettingsIn(BaseModel):
    max_failed_visits: int


class AgendaRow(BaseModel):
    project_id: uuid.UUID
    title: str
    status: ProjectStatus
    scheduled_date: date | None
    primary_technician_user_id: uuid.UUID | None
    address_street: str | None
    address_unit: str | None
    address_city: str | None
    case_id: uuid.UUID | None
    case_number: str | None
    stage_code: str | None
    substatus_code: str | None
    # Días de atraso si sigue sin cerrar y su fecha ya pasó (spec 2026-10-16).
    days_late: int | None = None
    # Jornadas del diario de obra. Más de una = obra de varios días, que es lo
    # que la Agenda marca (punto 4 del cuestionario).
    day_count: int = 0


class InstallationGapsResponse(BaseModel):
    can_close: bool
    missing: list[str]


class InspectionQueueRow(BaseModel):
    """Una fila de «Por revisar» › Inspección municipal."""
    project_id: uuid.UUID
    case_id: uuid.UUID | None
    case_number: str | None
    title: str
    customer_name: str | None
    completed_date: date | None
    status: str  # unscheduled | scheduled | failed
    scheduled_for: datetime | None
    days_since_close: int | None


class PendingReviewRow(BaseModel):
    """Una fila de «Actas por confirmar»."""
    project_id: uuid.UUID
    case_id: uuid.UUID | None
    case_number: str | None
    title: str
    customer_name: str | None
    technician_name: str | None
    completed_date: date | None
    days_waiting: int | None


# --- Módulo 5: inspección ----------------------------------------------------

class InspectionCreate(BaseModel):
    scheduled_for: datetime
    inspector_name: str | None = Field(default=None, max_length=255)


class InspectionResultRequest(BaseModel):
    result: str
    observations: str | None = Field(default=None, max_length=4000)
    inspector_name: str | None = Field(default=None, max_length=255)


class InspectionResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    scheduled_for: datetime
    inspector_name: str | None
    result: str
    result_recorded_at: datetime | None
    recorded_by_user_id: uuid.UUID | None
    observations: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class FieldCatalogsResponse(BaseModel):
    evidence_categories: dict[str, str]
    installation_conditions: dict[str, str]
    equipment_types: dict[str, str]
    permit_statuses: dict[str, str]
    inspection_results: dict[str, str]
    visit_failure_reasons: dict[str, str] = {}


class InstallerResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    model_config = {"from_attributes": True}


# --- Módulo 6: revisión del acta ---------------------------------------------

class ReturnToTechnicianRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class ProjectReviewResponse(BaseModel):
    id: uuid.UUID
    action: str
    reason: str | None
    actor_user_id: uuid.UUID | None
    created_at: datetime
    model_config = {"from_attributes": True}
