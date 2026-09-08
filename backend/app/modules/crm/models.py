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


class LeadStatus(str, enum.Enum):
    new = "new"
    contacted = "contacted"
    qualified = "qualified"
    disqualified = "disqualified"
    converted = "converted"


class ActivityType(str, enum.Enum):
    call = "call"
    email = "email"
    meeting = "meeting"
    note = "note"
    task = "task"
    follow_up = "follow_up"


class QuoteStatus(str, enum.Enum):
    draft = "draft"
    sent = "sent"
    accepted = "accepted"
    rejected = "rejected"
    expired = "expired"


# Funder / benefit-program vocabulary is intentionally free text (String), not
# an enum, because organizations run different program mixes (spec 4:
# "Configuration over hard coding") — e.g. CARE, MEDICAL, CALFRESH, HEEHRA,
# LADWP, TAXES, or a future program. Validated against an org-configurable
# list in the UI rather than the database schema.


# ---------------------------------------------------------------------------
# Customer / contacts
# ---------------------------------------------------------------------------

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

class Lead(UUIDPKMixin, TimestampMixin, OrgScopedMixin, PropertyAddressMixin, Base):
    __tablename__ = "leads"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(32))
    phone_normalized: Mapped[str | None] = mapped_column(String(32), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    email_normalized: Mapped[str | None] = mapped_column(String(255), index=True)
    source: Mapped[str | None] = mapped_column(String(100))
    benefit_type: Mapped[str | None] = mapped_column(String(100))  # CARE / MEDICAL / CALFRESH / ...
    funder_program: Mapped[str | None] = mapped_column(String(100))  # HEEHRA / LADWP / ...
    interested_service: Mapped[str | None] = mapped_column(String(255))
    assigned_owner_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    status: Mapped[LeadStatus] = mapped_column(
        Enum(LeadStatus, name="lead_status"), default=LeadStatus.new, nullable=False
    )
    notes: Mapped[str | None] = mapped_column(Text)
    converted_customer_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    converted_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(GUID())


# ---------------------------------------------------------------------------
# Pipeline stages (org-configurable, spec 7.1) and opportunities
# ---------------------------------------------------------------------------

class PipelineStage(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_pipeline_stage_org_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


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


class Opportunity(UUIDPKMixin, TimestampMixin, OrgScopedMixin, PropertyAddressMixin, Base):
    __tablename__ = "opportunities"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    primary_contact_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    estimated_amount: Mapped[float | None] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    probability: Mapped[int | None] = mapped_column(Integer)
    expected_close_date: Mapped[date | None] = mapped_column(Date)
    stage_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("pipeline_stages.id"), nullable=False, index=True)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    loss_reason: Mapped[str | None] = mapped_column(String(255))

    # Funder-program specific fields (confirmed domain model).
    benefit_type: Mapped[str | None] = mapped_column(String(100))
    funder_program: Mapped[str | None] = mapped_column(String(100))
    application_number: Mapped[str | None] = mapped_column(String(100))
    approval_code: Mapped[str | None] = mapped_column(String(100))
    funder_status_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("funder_statuses.id"), index=True
    )

    # Extra intake fields captured on the real forms (confirmed with Mateo
    # Sept 2026), previously only tracked in the manual spreadsheets.
    utility_account_number: Mapped[str | None] = mapped_column(String(100))
    meter_number: Mapped[str | None] = mapped_column(String(100))
    unit_type: Mapped[str | None] = mapped_column(String(100))  # mobile home / apartment / house size, etc.
    scheduled_install_date: Mapped[date | None] = mapped_column(Date)

    source_lead_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    stage: Mapped["PipelineStage"] = relationship("PipelineStage", lazy="joined")
    funder_status: Mapped["FunderStatus | None"] = relationship("FunderStatus", lazy="joined")


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------

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

class Quote(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "quotes"

    quote_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False)
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)
    project_description: Mapped[str | None] = mapped_column(Text)
    issue_date: Mapped[date | None] = mapped_column(Date)
    expiry_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus, name="quote_status"), default=QuoteStatus.draft, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    line_items: Mapped[list["QuoteLineItem"]] = relationship(
        "QuoteLineItem", back_populates="quote", cascade="all, delete-orphan", order_by="QuoteLineItem.sort_order",
        lazy="selectin",
    )


class QuoteLineItem(UUIDPKMixin, Base):
    __tablename__ = "quote_line_items"

    quote_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(10, 2), default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    discount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tax_value: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    quote: Mapped["Quote"] = relationship("Quote", back_populates="line_items")
