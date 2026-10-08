"""Contratos de entrada y salida del expediente."""
import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, computed_field

from app.modules.cases import stages


class CaseCreateRequest(BaseModel):
    """Abrir un expediente = registrar una puerta tocada.

    `stage_code` es el resultado del primer toque, así que solo admite las
    cuatro etapas iniciales. El cliente no se pide aquí: si nadie abrió, no hay
    a quién pedirle datos."""

    stage_code: str = Field(description="Una de: " + ", ".join(sorted(stages.INITIAL_STAGES)))
    source: str = "visit"

    address_street: str | None = Field(default=None, max_length=255)
    address_unit: str | None = Field(default=None, max_length=50)
    address_city: str | None = Field(default=None, max_length=120)
    address_state: str | None = Field(default=None, max_length=2)
    address_zip: str | None = Field(default=None, max_length=10)
    latitude: float | None = None
    longitude: float | None = None

    customer_id: uuid.UUID | None = None
    program_id: uuid.UUID | None = None


class CaseTransitionRequest(BaseModel):
    to_stage: str
    reason: str | None = Field(default=None, max_length=2000)
    substatus: str | None = None
    # Al aprobar: lo que devuelve el programa. Sin código de aprobación el
    # cobro no se puede radicar (requisito del módulo 6).
    approval_code: str | None = Field(default=None, max_length=100)
    application_number: str | None = Field(default=None, max_length=100)


class CaseSubstatusRequest(BaseModel):
    substatus: str
    reason: str | None = Field(default=None, max_length=2000)


class CaseResponse(BaseModel):
    id: uuid.UUID
    case_number: str
    source: str
    stage_code: str
    # La etiqueta en español viaja con el dato para que el frontend no tenga que
    # repetir el diccionario de etapas ni desactualizarse cuando cambie.
    stage_label: str
    substatus_code: str | None
    stage_reason: str | None

    customer_id: uuid.UUID | None
    program_id: uuid.UUID | None
    assigned_salesperson_id: uuid.UUID | None
    assigned_admin_id: uuid.UUID | None

    address_street: str | None
    address_unit: str | None
    address_city: str | None
    address_state: str | None
    address_zip: str | None

    application_number: str | None
    approval_code: str | None
    funder_status_code: str | None

    first_contact_at: datetime | None
    submitted_at: datetime | None
    approved_at: datetime | None
    completed_at: datetime | None
    closed_at: datetime | None
    scheduled_install_date: date | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseStageEventResponse(BaseModel):
    id: uuid.UUID
    from_stage_code: str | None
    to_stage_code: str
    from_substatus_code: str | None
    to_substatus_code: str | None
    reason: str | None
    actor_user_id: uuid.UUID | None
    occurred_at: datetime

    model_config = {"from_attributes": True}

    # Las etiquetas viajan con el evento, como `stage_label` en el expediente:
    # el historial mostraba códigos internos («install_scheduled») cuando el
    # diccionario del frontend no conocía un sub-estado (QA-REG-08).
    @computed_field
    @property
    def to_stage_label(self) -> str:
        return stages.STAGE_LABELS.get(self.to_stage_code, self.to_stage_code)

    @computed_field
    @property
    def to_substatus_label(self) -> str | None:
        if not self.to_substatus_code:
            return None
        return stages.SUBSTATUS_LABELS.get(self.to_substatus_code, self.to_substatus_code)


class CaseActivityItem(BaseModel):
    """Un cambio de etapa reciente, listo para mostrar en el Inicio."""

    case_id: uuid.UUID
    case_number: str
    # Nulo mientras nadie abrió la puerta; entonces se muestra la dirección.
    customer_name: str | None
    address: str | None
    to_stage_code: str
    label: str
    reason: str | None
    # Nulo si lo hizo el sistema.
    actor_name: str | None
    occurred_at: datetime


class StageInfo(BaseModel):
    code: str
    label: str
    is_initial: bool
    substatuses: list[str]
    allowed_next: list[str]


class StageCatalogResponse(BaseModel):
    """El mapa completo del flujo, para que el frontend no lo repita.

    Con esto el tablero puede pintar las columnas en orden, saber qué botones de
    transición ofrecer desde la etapa actual y mostrar etiquetas en español, sin
    una sola constante duplicada en TypeScript."""

    stages: list[StageInfo]
