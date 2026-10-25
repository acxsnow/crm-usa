import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


# Estado del DOCUMENTO. El estado del pago (sin pagar, parcial, pagada,
# vencida) no se guarda: se calcula de los pagos, así nunca se desincroniza.
class DocumentStatus:
    draft = "draft"      # editable, sin número definitivo de uso externo
    issued = "issued"    # emitida: ya no se edita (spec D6.3)
    void = "void"        # anulada; si la reemplaza otra, lo dice replaces_invoice_id


class InvoiceKind:
    rebate = "rebate"          # cobro a un programa; el cliente no paga (D6.1)
    particular = "particular"  # trabajo que paga el cliente


LINE_KINDS = {
    "service": "Servicio",
    "equipment": "Equipo",
    "material": "Material",
    "labor": "Mano de obra",
    "permit": "Permiso",
    "rebate": "Rebate o incentivo",
    "other": "Otro",
}


class Invoice(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Documento de factura, común al cobro de rebate y al trabajo particular
    (spec D6.1).

    `amount` es lo COBRABLE, y contra eso se comparan los pagos:
    - rebate: la suma de los rebates, que paga el programa. Lo que "debe" el
      cliente (`customer_total`) queda en 0 por efecto administrativo.
    - particular: subtotal menos rebates, que paga el cliente.
    Con líneas, `amount` se recalcula de ellas; las facturas anteriores al
    módulo 6 no tienen líneas y conservan el monto que se les escribió."""

    __tablename__ = "invoices"

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default=InvoiceKind.particular)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cases.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # La factura que esta reemplaza (una emitida no se edita: se anula y se
    # emite otra que apunta a ella).
    replaces_invoice_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("invoices.id"))
    # El cobro de rebate al que pertenece (spec D6.3). Un cobro puede tener
    # varias facturas si se refacturó; la vigente es la que no está anulada.
    claim_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("rebate_claims.id"), index=True)
    # La cotización aceptada de la que salió (trabajo particular, spec D6.7).
    quote_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("quotes.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    funder_program: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    document_status: Mapped[str] = mapped_column(String(10), nullable=False, default=DocumentStatus.issued)
    issue_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    void_reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoiceLine.sort_order", lazy="selectin",
    )
    payments: Mapped[list["InvoicePayment"]] = relationship(
        "InvoicePayment", back_populates="invoice", cascade="all, delete-orphan",
        order_by="InvoicePayment.paid_at", lazy="selectin",
    )
    attachments: Mapped[list["InvoiceAttachment"]] = relationship(
        "InvoiceAttachment", back_populates="invoice", cascade="all, delete-orphan", lazy="selectin",
    )

    # --- Totales (Decimal siempre; ver billing/money.py) ---------------------

    @property
    def subtotal(self) -> Decimal:
        from app.modules.billing.money import money_sum

        if not self.lines:
            return to_decimal(self.amount)
        return money_sum(l.amount for l in self.lines if l.kind != "rebate")

    @property
    def rebate_total(self) -> Decimal:
        from app.modules.billing.money import money_sum

        return money_sum(l.amount for l in self.lines if l.kind == "rebate")

    @property
    def customer_total(self) -> Decimal:
        """Lo que queda a cargo del cliente. En rebate es 0 (administrativo)."""
        return (self.subtotal - self.rebate_total).quantize(Decimal("0.01"))

    @property
    def paid_amount(self) -> Decimal:
        from app.modules.billing.money import money_sum

        return money_sum(p.amount for p in self.payments)

    @property
    def balance(self) -> Decimal:
        return (to_decimal(self.amount) - self.paid_amount).quantize(Decimal("0.01"))

    def payment_status_on(self, today: date) -> str:
        """Estado del pago a una fecha (la de la organización, ver
        `field_ops/clock.py`). Anulada o borrador no tienen estado de pago."""
        if self.document_status != DocumentStatus.issued:
            return self.document_status
        if self.paid_amount > 0 and self.balance <= 0:
            return "paid"
        if self.due_date and self.due_date < today:
            return "overdue"
        if self.paid_amount > 0:
            return "partial"
        return "unpaid"


def to_decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


class InvoiceLine(UUIDPKMixin, Base):
    """Una línea de la factura. `amount` = cantidad × precio, redondeado a
    centavos al guardarse (lo calcula el servicio, no el cliente)."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="service")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    service_code: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")


class InvoicePayment(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "invoice_payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    paid_at: Mapped[date] = mapped_column(Date, nullable=False)
    method: Mapped[str | None] = mapped_column(String(100))
    reference: Mapped[str | None] = mapped_column(String(255))
    notes: Mapped[str | None] = mapped_column(Text)
    # Pagos en línea (payments/): quién lo procesó, su id allá (el PaymentIntent
    # de Stripe, para reconocer reembolsos y reintentos) y la comisión cobrada.
    provider: Mapped[str | None] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(255), index=True)
    fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))

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


class DocumentSequence(UUIDPKMixin, OrgScopedMixin, Base):
    """Contador de numeración por organización, serie y año (ver
    `billing/numbering.py`)."""

    __tablename__ = "document_sequences"
    __table_args__ = (
        UniqueConstraint("organization_id", "series", "year", name="uq_document_sequence"),
    )

    series: Mapped[str] = mapped_column(String(10), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


# ---------------------------------------------------------------------------
# Configuración de cobro por programa (spec D6.2). Apunta a `Program` (de la
# Cadena A) y no lo modifica.
# ---------------------------------------------------------------------------

class BillingProgramProfile(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Datos de la factura y umbral de alerta de un programa."""

    __tablename__ = "billing_program_profiles"
    __table_args__ = (UniqueConstraint("organization_id", "program_id", name="uq_billing_profile_program"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Entidad que factura (Delta HVAC Service Inc. o Desert Alliance
    # Properties LLC según el programa; pendiente de confirmar con el cliente).
    issuer_name: Mapped[str | None] = mapped_column(String(255))
    issuer_address: Mapped[str | None] = mapped_column(String(500))
    issuer_phone: Mapped[str | None] = mapped_column(String(50))
    issuer_email: Mapped[str | None] = mapped_column(String(255))
    legal_text: Mapped[str | None] = mapped_column(Text)
    # Días que normalmente tarda el programa en pagar: pasado eso, alerta.
    expected_payment_days: Mapped[int] = mapped_column(Integer, nullable=False, default=45)


class ProgramRebateRate(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Lo que paga el programa por dirección, con vigencia. Cambia cada año
    (TECH $4.000 este año, puede subir el próximo)."""

    __tablename__ = "program_rebate_rates"

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class ProgramJurisdiction(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Dónde aplica un programa, con vigencia (TECH es San Fernando este año y
    puede ser otra zona el próximo). Por ciudad o código postal."""

    __tablename__ = "program_jurisdictions"

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # city | zip
    value: Mapped[str] = mapped_column(String(120), nullable=False, index=True)  # normalizado
    label: Mapped[str] = mapped_column(String(120), nullable=False)  # como lo escribió la persona
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date)

    def covers(self, day: date) -> bool:
        return self.valid_from <= day and (self.valid_to is None or day <= self.valid_to)


class ProgramClaimRequirement(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un requisito para radicar el cobro de un programa. `auto` se comprueba
    con datos (catálogo en `billing/requirements.py`); `manual` lo confirma una
    persona en cada cobro."""

    __tablename__ = "program_claim_requirements"
    __table_args__ = (UniqueConstraint("program_id", "code", name="uq_program_requirement_code"),)

    program_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # auto | manual
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


# ---------------------------------------------------------------------------
# Cobro de rebate (spec D6.3): un cobro por programa y por instalación.
# ---------------------------------------------------------------------------

class ClaimStatus:
    preparing = "preparing"  # creado, reuniendo requisitos; aún no radicado
    submitted = "submitted"  # radicado ante el programa, esperando respuesta
    rejected = "rejected"    # el programa lo rechazó: en corrección, sin vencimiento
    paid = "paid"            # el programa pagó (puede haber diferencia)
    withdrawn = "withdrawn"  # retirado con motivo; libera el programa


CLAIM_STATUS_LABELS = {
    "preparing": "Por radicar",
    "submitted": "Radicado",
    "rejected": "Rechazado, en corrección",
    "paid": "Pagado",
    "withdrawn": "Retirado",
}

REJECTION_CATEGORIES = {
    "documentary": "Documental",
    "technical": "Técnico",
    "other": "Otro",
}


class RebateClaim(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """El cobro de un programa por una instalación.

    Congela al crearse la tarifa vigente en la fecha de la instalación y el
    resultado de la jurisdicción: un cambio posterior en la configuración del
    programa no altera cobros existentes."""

    __tablename__ = "rebate_claims"
    __table_args__ = (
        # Un cobro vivo por programa e instalación. Parcial: uno retirado
        # libera el programa. Además del chequeo del servicio, la base impide
        # que dos creaciones simultáneas dejen dos cobros.
        Index(
            "uq_rebate_claim_active", "project_id", "program_id", unique=True,
            postgresql_where=text("status <> 'withdrawn'"), sqlite_where=text("status <> 'withdrawn'"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    case_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("cases.id"), index=True)
    program_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("programs.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=ClaimStatus.preparing, index=True)
    # Tarifa congelada y la fecha de instalación con la que se eligió.
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    rate_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("program_rebate_rates.id", ondelete="SET NULL"))
    installation_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Jurisdicción: si la dirección estaba en la zona del programa ese día. Si
    # no, el cobro se crea igual con el motivo (casos de borde que el programa
    # acepta).
    applies: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    jurisdiction_label: Mapped[str | None] = mapped_column(String(120))
    override_reason: Mapped[str | None] = mapped_column(Text)
    # Pago del programa.
    paid_on: Mapped[date | None] = mapped_column(Date)
    paid_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    payment_reference: Mapped[str | None] = mapped_column(String(255))
    withdrawn_reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    program = relationship("Program", lazy="selectin", viewonly=True)
    attempts: Mapped[list["RebateClaimAttempt"]] = relationship(
        "RebateClaimAttempt", back_populates="claim", cascade="all, delete-orphan",
        order_by="RebateClaimAttempt.created_at", lazy="selectin",
    )
    checks: Mapped[list["RebateClaimCheck"]] = relationship(
        "RebateClaimCheck", back_populates="claim", cascade="all, delete-orphan", lazy="selectin",
    )
    invoices: Mapped[list["Invoice"]] = relationship(
        "Invoice", primaryjoin="Invoice.claim_id == RebateClaim.id", foreign_keys="Invoice.claim_id",
        order_by="Invoice.created_at", lazy="selectin", viewonly=True,
    )

    @property
    def invoice(self) -> "Invoice | None":
        """La factura vigente: la última que no está anulada."""
        vigentes = [i for i in self.invoices if i.document_status != DocumentStatus.void]
        return vigentes[-1] if vigentes else None

    @property
    def difference(self) -> Decimal | None:
        """Pagado menos esperado. Negativo: el programa pagó de menos."""
        if self.paid_amount is None:
            return None
        return (to_decimal(self.paid_amount) - to_decimal(self.amount)).quantize(Decimal("0.01"))

    @property
    def is_open(self) -> bool:
        return self.status in (ClaimStatus.preparing, ClaimStatus.submitted, ClaimStatus.rejected)


class RebateClaimAttempt(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Una radicación ante el programa y su resultado. Los rechazos quedan como
    intentos: es la métrica de rechazos por programa."""

    __tablename__ = "rebate_claim_attempts"

    claim_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rebate_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    submitted_on: Mapped[date] = mapped_column(Date, nullable=False)
    portal_reference: Mapped[str | None] = mapped_column(String(255))
    submitted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())
    result: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|paid|rejected
    rejection_category: Mapped[str | None] = mapped_column(String(20))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    resolved_on: Mapped[date | None] = mapped_column(Date)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    claim: Mapped["RebateClaim"] = relationship("RebateClaim", back_populates="attempts")


class RebateClaimCheck(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un requisito manual confirmado en un cobro (quién, cuándo, nota)."""

    __tablename__ = "rebate_claim_checks"
    __table_args__ = (UniqueConstraint("claim_id", "code", name="uq_rebate_claim_check"),)

    claim_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rebate_claims.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    confirmed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    claim: Mapped["RebateClaim"] = relationship("RebateClaim", back_populates="checks")


# ---------------------------------------------------------------------------
# Trabajo particular: cotización con versiones (spec D6.7). Cuelga del
# cliente y, si aplica, de una instalación. Nunca mueve el expediente.
# ---------------------------------------------------------------------------

class QuoteStatus:
    draft = "draft"            # editable
    sent = "sent"              # enviada al cliente, esperando respuesta
    accepted = "accepted"      # aceptada: ya tiene su factura
    rejected = "rejected"      # el cliente no la aceptó
    superseded = "superseded"  # reemplazada por una versión siguiente


QUOTE_STATUS_LABELS = {
    "draft": "Borrador",
    "sent": "Enviada",
    "accepted": "Aceptada",
    "rejected": "Rechazada",
    "superseded": "Reemplazada por otra versión",
    "expired": "Vencida",
}

DRAFT_INVOICE_NUMBER = "BORRADOR"


class Quote(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Una versión de una cotización. Todas las versiones comparten
    `quote_number` (COT-2026-0001) y se distinguen por `version`; ajustar crea
    la siguiente y la anterior queda como historial."""

    __tablename__ = "quotes"
    __table_args__ = (UniqueConstraint("organization_id", "quote_number", "version", name="uq_quote_version"),)

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    quote_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_version_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("quotes.id"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=QuoteStatus.draft, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    valid_until: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID())

    lines: Mapped[list["QuoteLine"]] = relationship(
        "QuoteLine", back_populates="quote", cascade="all, delete-orphan",
        order_by="QuoteLine.sort_order", lazy="selectin",
    )

    @property
    def total(self) -> Decimal:
        from app.modules.billing.money import money_sum

        rebates = money_sum(l.amount for l in self.lines if l.kind == "rebate")
        return money_sum(l.amount for l in self.lines if l.kind != "rebate") - rebates

    def status_on(self, today: date) -> str:
        """Vencida se calcula: una enviada cuya vigencia ya pasó."""
        if self.status == QuoteStatus.sent and self.valid_until and self.valid_until < today:
            return "expired"
        return self.status


class QuoteLine(UUIDPKMixin, Base):
    __tablename__ = "quote_lines"

    quote_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="service")
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    service_code: Mapped[str | None] = mapped_column(String(50))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    quote: Mapped["Quote"] = relationship("Quote", back_populates="lines")
