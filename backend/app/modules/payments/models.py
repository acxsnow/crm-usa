"""Cobro con tarjeta o banco (como Housecall Pro) y banca conectada (como el
«bank feed» de QuickBooks). Spec: docs/superpowers/specs/2026-10-25-pagos-tarjeta-design.md.

- Cobro: el cliente recibe un enlace a una página con su factura y paga en
  Stripe (tarjeta, Apple Pay, Google Pay o ACH). El pago entra a la factura
  solo, por el webhook firmado de Stripe. Ningún dato de tarjeta pasa por aquí.
- Banca: las tarjetas y cuentas de la empresa se conectan con Plaid. Sus
  movimientos llegan a «Por revisar»; Contabilidad los agrega como gasto de una
  obra, los hace coincidir con lo ya registrado o los excluye, y las reglas lo
  hacen solas con lo que se repite.
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

MONEY = Numeric(12, 2)


class PaymentLink(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un enlace de pago de una factura: el total pendiente o un anticipo.

    El enlace lleva a nuestra página pública (`/pagar/<token>`), que muestra la
    factura y abre Stripe con un pago nuevo cada vez: así el enlace no vence a
    las 24 h como las sesiones de Stripe. El token solo se guarda como hash."""

    __tablename__ = "payment_links"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoices.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    # full (lo que falte) | deposit (un monto fijo, p. ej. el 50 % de anticipo)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="full")
    amount: Mapped[Decimal | None] = mapped_column(MONEY)
    # active | processing (ACH en camino) | paid | failed | revoked
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sent_to_email: Mapped[str | None] = mapped_column(String(255))
    sent_to_phone: Mapped[str | None] = mapped_column(String(32))
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stripe_session_id: Mapped[str | None] = mapped_column(String(255))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))


class ProviderEvent(UUIDPKMixin, OrgScopedMixin, Base):
    """Cada evento de Stripe o Plaid ya procesado: un reintento no duplica."""

    __tablename__ = "provider_events"
    __table_args__ = (UniqueConstraint("provider", "event_id", name="uq_provider_event"),)

    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary: Mapped[dict | None] = mapped_column(JSON)


class BankConnection(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un banco conectado con Plaid (un «Item»). El token de acceso va cifrado."""

    __tablename__ = "bank_connections"

    institution_name: Mapped[str] = mapped_column(String(255), nullable=False)
    institution_id: Mapped[str | None] = mapped_column(String(80))
    plaid_item_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    # active | needs_login (hay que volver a entrar al banco) | disconnected
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(String(500))
    connected_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    accounts: Mapped[list["BankAccount"]] = relationship("BankAccount", lazy="selectin", cascade="all, delete-orphan",
                                                         order_by="BankAccount.name")


class BankAccount(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "bank_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "plaid_account_id", name="uq_bank_account_plaid"),)

    connection_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bank_connections.id", ondelete="CASCADE"),
                                                     nullable=False, index=True)
    plaid_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    mask: Mapped[str | None] = mapped_column(String(10))
    # depository (cuenta) | credit (tarjeta) | …
    type: Mapped[str | None] = mapped_column(String(30))
    subtype: Mapped[str | None] = mapped_column(String(40))
    current_balance: Mapped[Decimal | None] = mapped_column(MONEY)
    available_balance: Mapped[Decimal | None] = mapped_column(MONEY)
    currency: Mapped[str | None] = mapped_column(String(3))
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BankTransaction(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un movimiento de banco o tarjeta. `amount` en positivo es dinero que
    sale (compra, cargo); en negativo, dinero que entra (depósito), como lo
    entrega Plaid."""

    __tablename__ = "bank_transactions"
    __table_args__ = (
        UniqueConstraint("organization_id", "plaid_transaction_id", name="uq_bank_transaction_plaid"),
        Index("ix_bank_transactions_org_status_date", "organization_id", "review_status", "posted_date"),
    )

    account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("bank_accounts.id", ondelete="CASCADE"),
                                                  nullable=False, index=True)
    plaid_transaction_id: Mapped[str] = mapped_column(String(255), nullable=False)
    posted_date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    merchant_name: Mapped[str | None] = mapped_column(String(255))
    plaid_category: Mapped[str | None] = mapped_column(String(120))
    pending: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # review (Por revisar) | categorized (Categorizado) | excluded (Excluido)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="review")
    # Lo que proponen las reglas, para aceptar con un clic (como QuickBooks).
    suggested_category: Mapped[str | None] = mapped_column(String(30))
    suggested_project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    suggested_rule_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("bank_rules.id", ondelete="SET NULL"))
    # Qué quedó: un gasto nuevo o algo ya registrado con lo que coincidió.
    expense_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("expenses.id", ondelete="SET NULL"))
    matched_type: Mapped[str | None] = mapped_column(String(30))
    matched_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    category: Mapped[str | None] = mapped_column(String(30))
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    memo: Mapped[str | None] = mapped_column(String(500))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BankRule(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Regla bancaria (como en QuickBooks): si la descripción contiene un texto
    y el monto cae en el rango, propone la categoría y la obra; con
    `auto_add` la agrega sola."""

    __tablename__ = "bank_rules"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    contains: Mapped[str] = mapped_column(String(120), nullable=False)
    # out (gastos) | in (depósitos) | any
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="out")
    amount_min: Mapped[Decimal | None] = mapped_column(MONEY)
    amount_max: Mapped[Decimal | None] = mapped_column(MONEY)
    account_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("bank_accounts.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"))
    auto_add: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text)
