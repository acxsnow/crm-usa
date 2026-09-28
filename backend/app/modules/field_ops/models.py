import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID
from app.modules.crm.models import PropertyAddressMixin


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ProjectStatus(str, enum.Enum):
    planning = "planning"
    scheduled = "scheduled"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    done = "done"


# ---------------------------------------------------------------------------
# Project (one per property/space — confirmed domain model)
# ---------------------------------------------------------------------------

class Project(UUIDPKMixin, TimestampMixin, OrgScopedMixin, PropertyAddressMixin, Base):
    __tablename__ = "projects"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # El expediente del que nace el proyecto. Reemplazó a `opportunity_id`, que
    # se retiró junto con el modelo anterior.
    case_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cases.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"), default=ProjectStatus.planning, nullable=False
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    primary_technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    notes: Mapped[str | None] = mapped_column(Text)
    # Condiciones de ESTA casa que vuelven obligatorios ciertos ítems del
    # checklist (catálogo `INSTALLATION_CONDITIONS`, requerimientos §8.3).
    installation_conditions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


# ---------------------------------------------------------------------------
# Checklists — template (org-configurable) and per-project snapshot
# ---------------------------------------------------------------------------

class ChecklistTemplate(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "checklist_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100))
    # La plantilla de un programa concreto. Nula = la plantilla por defecto de
    # la organización, que se usa cuando el programa no tiene la suya.
    program_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="SET NULL"), index=True
    )

    items: Mapped[list["ChecklistTemplateItem"]] = relationship(
        "ChecklistTemplateItem", back_populates="template", cascade="all, delete-orphan",
        order_by="ChecklistTemplateItem.sort_order", lazy="selectin",
    )


class ChecklistTemplateItem(UUIDPKMixin, Base):
    __tablename__ = "checklist_template_items"

    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("checklist_templates.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    section: Mapped[str | None] = mapped_column(String(120))
    # Qué foto exige el ítem (catálogo `EVIDENCE_CATEGORIES`).
    evidence_category: Mapped[str | None] = mapped_column(String(40))
    # Solo es obligatorio si esta condición aplica a la instalación.
    condition_code: Mapped[str | None] = mapped_column(String(40))
    allows_not_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    template: Mapped["ChecklistTemplate"] = relationship("ChecklistTemplate", back_populates="items")


class ProjectChecklistItem(UUIDPKMixin, TimestampMixin, Base):
    """A snapshot copy of a template item at the moment it was applied to a
    project — later template edits must never mutate an in-progress project's
    checklist (spec 17 phase 3)."""

    __tablename__ = "project_checklist_items"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_template_item_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_evidence: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    section: Mapped[str | None] = mapped_column(String(120))
    evidence_category: Mapped[str | None] = mapped_column(String(40))
    condition_code: Mapped[str | None] = mapped_column(String(40))
    allows_not_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    # "No aplica" siempre con motivo: si el equipo no existe se deja constancia,
    # no se deja el ítem en blanco (requerimientos §8.3).
    not_applicable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    not_applicable_reason: Mapped[str | None] = mapped_column(Text)

    def counts_as_required(self, conditions: list[str]) -> bool:
        """Si este ítem bloquea el cierre de ESTA instalación."""
        if not self.is_required:
            return False
        return self.condition_code is None or self.condition_code in conditions

    @property
    def is_resolved(self) -> bool:
        return bool(self.is_complete or self.not_applicable)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class Task(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "field_tasks"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus, name="task_status"), default=TaskStatus.pending, nullable=False)
    assigned_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_overdue(self) -> bool:
        """Derived, not stored: unlike Invoice, TaskStatus has no separate
        "overdue" state to transition into (pending/in_progress/done cover
        the whole lifecycle), so this is computed on every read instead —
        same lazy-evaluation approach as Invoice._refresh_overdue_status,
        just without a status mutation to persist."""
        if self.status == TaskStatus.done or not self.due_date:
            return False
        from app.shared.datetime_utils import as_utc

        return as_utc(self.due_date) < datetime.now(timezone.utc)


class TaskComment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "task_comments"

    task_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("field_tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)


# ---------------------------------------------------------------------------
# Evidence — photos/videos. Confirmed requirement: GPS is captured whenever
# the browser allows it, and burned as a VISIBLE watermark into the image
# (not just stored as metadata) — see watermark.py.
# ---------------------------------------------------------------------------

class Evidence(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "evidence"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("field_tasks.id"), index=True)
    checklist_item_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("project_checklist_items.id"))
    # Código del catálogo `EVIDENCE_CATEGORIES`. Texto y no enum de Postgres:
    # agregar una categoría no debe exigir una migración.
    category: Mapped[str] = mapped_column(String(40), default="additional_photo", nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)  # storage-relative path
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watermarked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Attestation — digital signature capture (technician + customer), embedded
# into the generated attestation PDF. Confirmed requirement: replaces the
# paper signature sections on the current forms; must be app-signed, not a
# scanned/uploaded signature image of a paper form.
# ---------------------------------------------------------------------------

class Attestation(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "attestations"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    technician_signature_path: Mapped[str | None] = mapped_column(String(500))
    technician_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_name: Mapped[str | None] = mapped_column(String(255))
    customer_signature_path: Mapped[str | None] = mapped_column(String(500))
    customer_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pdf_path: Mapped[str | None] = mapped_column(String(500))
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_fully_signed(self) -> bool:
        return bool(self.technician_signed_at and self.customer_signed_at)


class CustomerSignatureToken(UUIDPKMixin, TimestampMixin, Base):
    """Hashed, single-use link allowing a customer to sign without CRM access."""
    __tablename__ = "customer_signature_tokens"

    attestation_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("attestations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------------------
# Módulo 5 — permiso municipal, inspección, equipos y materiales
# ---------------------------------------------------------------------------

class Permit(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Permiso municipal de una instalación. Solo registro: el trámite se hace
    en el portal de la ciudad. Puede haber varios por proyecto (eléctrico y
    mecánico, por ejemplo)."""

    __tablename__ = "permits"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permit_number: Mapped[str | None] = mapped_column(String(100))
    # Ciudad o condado que lo emite.
    jurisdiction: Mapped[str] = mapped_column(String(150), nullable=False)
    permit_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    filed_on: Mapped[date | None] = mapped_column(Date)
    approved_on: Mapped[date | None] = mapped_column(Date)
    expires_on: Mapped[date | None] = mapped_column(Date)
    not_required_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    def is_expired_on(self, day: date) -> bool:
        """Calculado, no guardado, como `Task.is_overdue`: un estado "vencido"
        necesitaría una tarea que lo actualice y, si no corre, el dato miente.
        Recibe el día porque "hoy" es el de la organización, no el del
        servidor (`field_ops/clock.py`)."""
        return self.expires_on is not None and self.expires_on < day

    def is_cleared_on(self, day: date) -> bool:
        """Si este permiso deja avanzar a "Listo para instalar"."""
        from app.modules.field_ops.catalogs import PermitStatus

        if self.status == PermitStatus.not_required:
            return True
        return self.status == PermitStatus.approved and not self.is_expired_on(day)


class Inspection(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un intento de inspección. Los fallidos se conservan: son el único dato
    para medir cuántas inspecciones fallan."""

    __tablename__ = "inspections"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    inspector_name: Mapped[str | None] = mapped_column(String(255))
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    result_recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    observations: Mapped[str | None] = mapped_column(Text)


class InstalledEquipment(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Equipo instalado como dato. El cobro al programa necesita marca, modelo y
    serial, no solo la foto de la etiqueta."""

    __tablename__ = "installed_equipment"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str | None] = mapped_column(String(100), index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    # En qué unidad o espacio quedó (casa principal, espacio 14…).
    unit_label: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())


class ProjectMaterial(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Lo que la orden necesita (PDF §5.1). No es inventario."""

    __tablename__ = "project_materials"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    sku: Mapped[str | None] = mapped_column(String(100))
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
