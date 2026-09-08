import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class InvoiceStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class Invoice(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Manual record of a funder reimbursement (or a paid non-program job),
    one per Project — confirmed with Mateo (Sept 2026): reimbursement is
    tracked per installation, matching "one Project per property/space".
    No generated pro-forma PDF in the MVP (spec 18 item 4, confirmed manual-
    record-only); this replaces the manual spreadsheet income tracking."""

    __tablename__ = "invoices"

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    funder_program: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.pending, nullable=False
    )
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    payments: Mapped[list["InvoicePayment"]] = relationship(
        "InvoicePayment", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoicePayment.paid_at", lazy="selectin",
    )
    attachments: Mapped[list["InvoiceAttachment"]] = relationship(
        "InvoiceAttachment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin",
    )

    @property
    def paid_amount(self) -> float:
        return round(sum(float(p.amount) for p in self.payments), 2)

    @property
    def balance(self) -> float:
        return round(float(self.amount) - self.paid_amount, 2)


class InvoicePayment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoice_payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")


class InvoiceAttachment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoice_attachments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    uploaded_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="attachments")
