"""Gastos de campo, cuentas por pagar y conciliación bancaria.

Spec: `docs/superpowers/specs/2026-10-13-modulos-gastos-proveedores-finanzas-design.md`.
Dinero siempre `Numeric(12, 2)` y `Decimal` (`billing/money.py`).
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------

EXPENSE_CATEGORIES = {
    "fuel": "Gasolina", "per_diem": "Viáticos", "lodging": "Hotel", "meals": "Comida",
    "tolls_parking": "Peajes y parqueo", "small_materials": "Material menor", "tools": "Herramienta",
    "other": "Otro",
}
EXPENSE_PAYMENT = {"own_money": "Dinero propio (se reembolsa)", "company_card": "Tarjeta de la empresa"}
EXPENSE_STATUSES = {"submitted": "Por revisar", "approved": "Aprobado", "rejected": "Rechazado",
                    "reimbursed": "Reembolsado"}
SUPPLIER_KINDS = {"equipment": "Equipos", "electrical": "Material eléctrico", "contractor": "Contratista",
                  "services": "Servicios", "other": "Otros"}
PAYMENT_METHODS = {"check": "Cheque", "ach": "ACH", "transfer": "Transferencia", "card": "Tarjeta de crédito",
                   "zelle": "Zelle", "cash": "Efectivo"}
COST_CATEGORIES = {"equipment": "Equipos", "materials": "Materiales", "contractor": "Contratistas",
                   "permit": "Permisos", "services": "Servicios", "other": "Otros"}
SUPPLIER_DOC_KINDS = {"w9": "W-9", "license": "Licencia de contratista", "insurance": "Seguro",
                      "contract": "Contrato", "other": "Otro"}
INVOICE_STATUSES = {"pending_approval": "Por aprobar", "approved": "Aprobada", "partially_paid": "Pagada en parte",
                    "paid": "Pagada", "void": "Anulada"}


# ---------------------------------------------------------------------------
# Gastos de campo
# ---------------------------------------------------------------------------

class Expense(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (Index("ix_expenses_org_status", "organization_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False, default="own_money")
    receipt_path: Mapped[str | None] = mapped_column(String(500))
    receipt_mime: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="submitted")
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    reimbursed_at: Mapped[date | None] = mapped_column(Date)
    reimbursement_reference: Mapped[str | None] = mapped_column(String(120))


# ---------------------------------------------------------------------------
# Proveedores y cuentas por pagar
# ---------------------------------------------------------------------------

class Supplier(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_supplier_name"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tax_id: Mapped[str | None] = mapped_column(String(40))
    kinds: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(500))
    states: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    payment_terms_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    payment_method: Mapped[str | None] = mapped_column(String(20))
    bank_details: Mapped[str | None] = mapped_column(Text)
    license_number: Mapped[str | None] = mapped_column(String(80))
    license_expires_on: Mapped[date | None] = mapped_column(Date)
    insurance_expires_on: Mapped[date | None] = mapped_column(Date)
    w9_on_file: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupplierDocument(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "supplier_documents"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("suppliers.id", ondelete="CASCADE"), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    expires_on: Mapped[date | None] = mapped_column(Date)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())


class SupplierInvoice(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "supplier_invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "supplier_id", "number", name="uq_supplier_invoice_number"),
        Index("ix_supplier_invoices_due", "organization_id", "status", "due_date"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id"), nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(80), nullable=False)
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    shipping: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_approval")
    scheduled_payment_date: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_mime: Mapped[str | None] = mapped_column(String(100))
    void_reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    lines: Mapped[list["SupplierInvoiceLine"]] = relationship(
        "SupplierInvoiceLine", cascade="all, delete-orphan", lazy="selectin", order_by="SupplierInvoiceLine.sort_order")
    approvals: Mapped[list["SupplierInvoiceApproval"]] = relationship(
        "SupplierInvoiceApproval", cascade="all, delete-orphan", lazy="selectin",
        order_by="SupplierInvoiceApproval.approved_at")
    allocations: Mapped[list["SupplierPaymentAllocation"]] = relationship(
        "SupplierPaymentAllocation", lazy="selectin", viewonly=True)


class SupplierInvoiceLine(UUIDPKMixin, Base):
    __tablename__ = "supplier_invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="materials")
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    # A qué instalación se carga el costo (rentabilidad). Vacío = gasto general.
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)


class SupplierInvoiceApproval(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "supplier_invoice_approvals"
    __table_args__ = (UniqueConstraint("invoice_id", "user_id", name="uq_supplier_invoice_approval_user"),)

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    # Con qué permiso aprobó: «approve» (Aldo / Gerencia) o «accounting» (Contabilidad).
    capacity: Mapped[str] = mapped_column(String(20), nullable=False)
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(500))


class SupplierPayment(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "supplier_payments"

    supplier_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("suppliers.id"), nullable=False, index=True)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    bank_account: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))
    file_mime: Mapped[str | None] = mapped_column(String(100))
    recorded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    allocations: Mapped[list["SupplierPaymentAllocation"]] = relationship(
        "SupplierPaymentAllocation", cascade="all, delete-orphan", lazy="selectin")


class SupplierPaymentAllocation(UUIDPKMixin, Base):
    __tablename__ = "supplier_payment_allocations"
    __table_args__ = (UniqueConstraint("payment_id", "invoice_id", name="uq_supplier_payment_invoice"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_payments.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("supplier_invoices.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class FinanceSettings(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "finance_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_finance_settings_org"),)

    # Desde este total una factura necesita dos aprobaciones (respuesta 2.1: 10.000 USD).
    two_approval_threshold: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("10000"))
    due_alert_days: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    document_alert_days: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_expense_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("5000"))


# ---------------------------------------------------------------------------
# Conciliación bancaria
# ---------------------------------------------------------------------------

class BankStatement(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "bank_statements"

    account_label: Mapped[str] = mapped_column(String(120), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    imported_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())


class BankStatementLine(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "bank_statement_lines"
    __table_args__ = (Index("ix_bank_lines_status", "organization_id", "status"),)

    statement_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("bank_statements.id", ondelete="CASCADE"), nullable=False, index=True)
    line_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    reference: Mapped[str | None] = mapped_column(String(120))
    # Positivo = entró dinero; negativo = salió.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="unmatched")  # unmatched|matched|ignored
    # Con qué movimiento registrado cuadra: invoice_payment | supplier_payment | expense
    matched_type: Mapped[str | None] = mapped_column(String(30))
    matched_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    matched_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    matched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_matched: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[str | None] = mapped_column(String(500))
