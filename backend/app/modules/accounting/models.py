"""Contabilidad de doble partida para reemplazar QuickBooks.

Los asientos automáticos llevan `source_key` (el documento del que nacen); los
manuales no. Un asiento no se edita ni se borra: se reversa con otro.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

MONEY = Numeric(14, 2)
ACCOUNT_TYPES = {"asset": "Activo", "liability": "Pasivo", "equity": "Patrimonio", "income": "Ingreso",
                 "cogs": "Costo de ventas", "expense": "Gasto"}
# Naturaleza débito: el saldo es débitos − créditos; las demás, al revés.
DEBIT_NORMAL = {"asset", "cogs", "expense"}


class Account(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "accounting_accounts"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_accounting_account_code"),
                      UniqueConstraint("organization_id", "system_key", name="uq_accounting_account_system"))

    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Las que usan los asientos automáticos; no se desactivan ni cambian de tipo.
    system_key: Mapped[str | None] = mapped_column(String(40))
    # Renglón del resumen para impuestos (lo valida el contador).
    tax_category: Mapped[str | None] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class JournalEntry(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "journal_entries"
    __table_args__ = (UniqueConstraint("organization_id", "source_key", "revision", name="uq_journal_source_revision"),
                      UniqueConstraint("organization_id", "number", name="uq_journal_number"),
                      Index("ix_journal_entries_org_date", "organization_id", "entry_date"))

    number: Mapped[str] = mapped_column(String(30), nullable=False)
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)
    memo: Mapped[str] = mapped_column(String(500), nullable=False)
    # p. ej. «invoice:<id>». Nulo = asiento manual.
    source_key: Mapped[str | None] = mapped_column(String(80), index=True)
    # La fecha del documento: un período cerrado corre `entry_date`, no el documento.
    source_date: Mapped[date | None] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    reversal_of_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("journal_entries.id"))
    reversed_by_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("journal_entries.id"))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["JournalLine"]] = relationship(
        "JournalLine", cascade="all, delete-orphan", lazy="selectin", order_by="JournalLine.sort_order")


class JournalLine(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "journal_lines"
    __table_args__ = (Index("ix_journal_lines_org_account", "organization_id", "account_id"),)

    entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("accounting_accounts.id"), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    debit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    memo: Mapped[str | None] = mapped_column(String(255))


class AccountingSettings(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "accounting_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_accounting_settings_org"),)

    # Cierre contable: nada se registra con fecha igual o anterior.
    locked_through: Mapped[date | None] = mapped_column(Date)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
