import enum
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
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


class EvidenceCategory(str, enum.Enum):
    before = "before"
    during = "during"
    after = "after"
    damage = "damage"
    other = "other"


# ---------------------------------------------------------------------------
# Project (one per property/space — confirmed domain model)
# ---------------------------------------------------------------------------

class Project(UUIDPKMixin, TimestampMixin, OrgScopedMixin, PropertyAddressMixin, Base):
    __tablename__ = "projects"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("opportunities.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status"), default=ProjectStatus.planning, nullable=False
    )
    scheduled_date: Mapped[date | None] = mapped_column(Date)
    completed_date: Mapped[date | None] = mapped_column(Date)
    primary_technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    notes: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Checklists — template (org-configurable) and per-project snapshot
# ---------------------------------------------------------------------------

class ChecklistTemplate(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "checklist_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(100))

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
    is_complete: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())


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
    category: Mapped[EvidenceCategory] = mapped_column(Enum(EvidenceCategory, name="evidence_category"), default=EvidenceCategory.other, nullable=False)
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
