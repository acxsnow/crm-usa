import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------

class CustomerType(str, enum.Enum):
    individual = "individual"
    business = "business"


class CustomerStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class ActivityType(str, enum.Enum):
    call = "call"
    email = "email"
    meeting = "meeting"
    note = "note"
    task = "task"
    follow_up = "follow_up"


class Customer(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "customers"

    legal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_type: Mapped[CustomerType] = mapped_column(
        Enum(CustomerType, name="customer_type"), default=CustomerType.individual, nullable=False
    )
    main_phone: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    billing_address: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(CustomerStatus, name="customer_status"), default=CustomerStatus.active, nullable=False
    )
    tags: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)

    contacts: Mapped[list["CustomerContact"]] = relationship(
        "CustomerContact", back_populates="customer", cascade="all, delete-orphan", lazy="selectin"
    )


class CustomerContact(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "customer_contacts"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(150))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    preferred_contact_method: Mapped[str | None] = mapped_column(String(50))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="contacts")


# ---------------------------------------------------------------------------
# Applications — one customer may have several program applications.
# ---------------------------------------------------------------------------

class Application(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "applications"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("customers.id", ondelete="SET NULL"), index=True)
    program_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    form_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, server_default="draft", index=True)
    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    terms_version: Mapped[str | None] = mapped_column(String(50))
    terms_accepted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    terms_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_signature_path: Mapped[str | None] = mapped_column(String(500))
    customer_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    salesperson_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    salesperson_signed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProgramFormField(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Configurable question/document/photo requirement for one program."""
    __tablename__ = "program_form_fields"

    program_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    form_version: Mapped[str] = mapped_column(String(50), nullable=False, server_default="1")
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    field_type: Mapped[str] = mapped_column(String(30), nullable=False, server_default="text")
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    options: Mapped[list | None] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ApplicationDocument(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "application_documents"

    application_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True)
    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)


# ---------------------------------------------------------------------------
# Property address (embedded, reused by Lead/Opportunity; Project in phase 3
# is one-per-property/space per the confirmed domain model)
# ---------------------------------------------------------------------------

class PropertyAddressMixin:
    address_street: Mapped[str | None] = mapped_column(String(255))
    address_unit: Mapped[str | None] = mapped_column(String(50))  # "Spc 176", trailer/unit number
    address_city: Mapped[str | None] = mapped_column(String(120))
    address_state: Mapped[str | None] = mapped_column(String(2))
    address_zip: Mapped[str | None] = mapped_column(String(10))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

class FunderStatus(UUIDPKMixin, OrgScopedMixin, Base):
    """Org-configurable catalog of funder/program approval statuses (what the
    funder reports back — CARE/MEDICAL/CALFRESH/HEEHRA/LADWP, etc). Separate
    from PipelineStage, which tracks our own process step (confirmed with
    Mateo Sept 2026 — replaces the earlier free-text funder_status field)."""

    __tablename__ = "funder_statuses"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_funder_status_org_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Activity(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "activities"

    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType, name="activity_type"), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    owner_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False, index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)


# ---------------------------------------------------------------------------
# Quotes (kept per spec 7.2; optional in the funder-program path — an
# Opportunity can go straight from "Aprobada" to a Project without a Quote)
# ---------------------------------------------------------------------------

