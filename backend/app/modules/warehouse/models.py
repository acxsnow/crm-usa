"""Bodega: catálogo de materiales, ubicaciones, existencias y movimientos.

Diseño: `docs/superpowers/specs/2026-10-19-control-bodega-design.md`.

Tres ideas sostienen el módulo:

- El **saldo** (`warehouse_stock`) es la suma de los movimientos de una
  ubicación. Se guarda para no sumar el libro entero en cada pantalla, y se
  actualiza en la misma transacción que el movimiento: nunca se toca solo.
- El **libro** (`warehouse_movements`) no se edita ni se borra. Corregir un
  error es registrar el movimiento contrario.
- La **ubicación** separa la bodega de la camioneta de cada técnico, que es lo
  que permite «el sobrante queda en la camioneta» en las obras de más de dos
  días (respuesta 5 del cuestionario).

Dinero con `Numeric(12, 2)` y `Decimal` (`billing/money.py`); cantidades con
`Numeric(10, 2)`.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
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
QUANTITY = Numeric(10, 2)


class WarehouseLocation(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Dónde está el material: la bodega (una sola) o la camioneta de un técnico."""

    __tablename__ = "warehouse_locations"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_warehouse_location_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="warehouse")
    # Solo para las camionetas: a quién pertenece.
    technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class WarehouseItem(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un material del catálogo, con lo que cuesta y cuándo hay que reponer."""

    __tablename__ = "warehouse_items"
    __table_args__ = (
        UniqueConstraint("organization_id", "sku", name="uq_warehouse_item_sku"),
        Index("ix_warehouse_items_org_category", "organization_id", "category"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Referencia del proveedor. Puede venir vacía en el Excel; cuando está, es
    # lo que evita duplicar el artículo al importar dos veces.
    sku: Mapped[str | None] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="unit")
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    supplier_name: Mapped[str | None] = mapped_column(String(255))
    # Los equipos con serial propio (respuesta 12: «TODOS»).
    has_serial: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    min_quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    notes: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    movements: Mapped[list["WarehouseMovement"]] = relationship(
        "WarehouseMovement", back_populates="item", lazy="raise")


class WarehouseStock(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Saldo por (artículo, ubicación). Lo mueve solo `warehouse/service.py`."""

    __tablename__ = "warehouse_stock"
    __table_args__ = (
        UniqueConstraint("item_id", "location_id", name="uq_warehouse_stock_item_location"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_items.id", ondelete="CASCADE"), nullable=False, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_locations.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("0"))


class WarehouseMovement(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Libro de entradas y salidas. Append-only: nunca se edita ni se borra."""

    __tablename__ = "warehouse_movements"
    __table_args__ = (
        Index("ix_warehouse_movements_org_date", "organization_id", "movement_date"),
        Index("ix_warehouse_movements_org_item", "organization_id", "item_id"),
        # Con qué documento se hizo: la misma factura o el mismo conteo no se
        # aplican dos veces. Nulo = movimiento libre (a mano), y en Postgres y
        # SQLite varios nulos conviven sin chocar.
        UniqueConstraint("organization_id", "source_key", name="uq_warehouse_movement_source"),
    )

    item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_items.id"), nullable=False, index=True)
    location_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_locations.id"), nullable=False, index=True)
    # A dónde llegó el material en un traslado (bodega → camioneta).
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouse_locations.id"))
    movement_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # Con signo: positiva sube el saldo, negativa lo baja (ver `catalogs.py`).
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(MONEY)
    movement_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Factura, orden de salida o conteo del que nace el movimiento.
    reference: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    # La obra a la que se carga lo que sale (costo real, punto 3).
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    source_key: Mapped[str | None] = mapped_column(String(160))
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    item: Mapped["WarehouseItem"] = relationship("WarehouseItem", back_populates="movements", lazy="raise")


class WarehouseReleaseOrder(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """La orden de salida del punto 1: sin autorización el material no sale.

    El número (`SAL-2026-0001`) se asigna al mandarla a autorizar y no antes: un
    borrador que nadie envió no consume un número de la serie.

    Autorizar y rechazar comparten los mismos dos campos (`authorized_*`): son la
    misma decisión, y mirar el `status` dice cuál de las dos fue.
    """

    __tablename__ = "warehouse_release_orders"
    __table_args__ = (
        UniqueConstraint("organization_id", "number", name="uq_warehouse_release_number"),
        Index("ix_warehouse_release_org_status", "organization_id", "status"),
    )

    number: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador")
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    # De dónde sale el material: la bodega (respuesta 1: hay una sola).
    location_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouse_locations.id"), nullable=False,
                                                   index=True)
    # Quien arma la orden (el técnico) y a quién se le entrega si es otro.
    requested_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    needed_on: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authorized_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_reason: Mapped[str | None] = mapped_column(Text)
    delivered_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # D-BOD-4: sin existencias no se bloquea la entrega; el motivo queda escrito.
    shortage_note: Mapped[str | None] = mapped_column(Text)

    lines: Mapped[list["WarehouseReleaseLine"]] = relationship(
        "WarehouseReleaseLine", back_populates="order", lazy="raise")


class WarehouseReleaseLine(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un material pedido. Lo pedido y lo entregado se guardan por separado:
    cuando no había existencia, `quantity_delivered` queda por debajo."""

    __tablename__ = "warehouse_release_lines"
    __table_args__ = (Index("ix_warehouse_release_lines_org_order", "organization_id", "order_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_release_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouse_items.id"), nullable=False, index=True)
    quantity_requested: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False)
    # Nulo hasta que Bodega entrega.
    quantity_delivered: Mapped[Decimal | None] = mapped_column(QUANTITY)
    # El calibre: lo que cambia entre un trabajo y otro («3/8», «1/2»).
    spec_label: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)
    origin: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    order: Mapped["WarehouseReleaseOrder"] = relationship(
        "WarehouseReleaseOrder", back_populates="lines", lazy="raise")


class WarehouseKitTemplate(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """La lista predefinida del punto 2: lo que un tipo de trabajo siempre lleva.

    Es una plantilla, no un documento: al aplicarla sus renglones se **copian** a
    la orden de salida (o al presupuesto, fase 3). Por eso editarla después no
    cambia nada de lo ya pedido — igual que `checklist_templates` y
    `project_checklist_items`.
    """

    __tablename__ = "warehouse_kit_templates"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_warehouse_kit_name"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # El tipo de trabajo del proyecto («hvac_install», «pedestal»...). Es texto
    # libre, el mismo que ya guarda `projects.project_type`.
    project_type: Mapped[str | None] = mapped_column(String(100), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["WarehouseKitItem"]] = relationship(
        "WarehouseKitItem", back_populates="template", cascade="all, delete-orphan",
        order_by="WarehouseKitItem.sort_order", lazy="raise")


class WarehouseKitItem(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un renglón de la lista: qué material, cuánto y de qué calibre."""

    __tablename__ = "warehouse_kit_items"
    __table_args__ = (Index("ix_warehouse_kit_items_org_template", "organization_id", "template_id"),)

    template_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("warehouse_kit_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("warehouse_items.id"), nullable=False, index=True)
    # La cantidad sugerida: se cambia en cada copia sin tocar la plantilla.
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("1"))
    # El calibre sugerido («3/8», «1/2»).
    spec_label: Mapped[str | None] = mapped_column(String(60))
    # En qué parte del trabajo va («Unidad exterior», «Líneas»).
    section: Mapped[str | None] = mapped_column(String(120))
    # Lo que sí o sí hay que llevar: la lista funciona como chequeo.
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    template: Mapped["WarehouseKitTemplate"] = relationship(
        "WarehouseKitTemplate", back_populates="items", lazy="raise")


class ProjectBudget(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """El presupuesto de un proyecto (punto 3): lo que el supervisor estima antes
    de instalar.

    Se puede armar a mano o copiando una lista predefinida, y queda en `borrador`
    hasta que lo aprueban. Solo el aprobado (`aprobado`) es el que se compara con
    lo real; si después se aprueba otro del mismo proyecto, el anterior pasa a
    `reemplazado` en vez de borrarse, para poder ver qué se estimó al principio.
    """

    __tablename__ = "project_budgets"
    __table_args__ = (Index("ix_project_budgets_org_project", "organization_id", "project_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="borrador")
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    lines: Mapped[list["ProjectBudgetLine"]] = relationship(
        "ProjectBudgetLine", back_populates="budget", lazy="raise")


class ProjectBudgetLine(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un renglón del presupuesto: categoría, qué y cuánto.

    El artículo del catálogo es **opcional**: la mano de obra o un permiso se
    presupuestan con su descripción, y solo el material y el equipo salen del
    catálogo. `amount` se guarda y no se recalcula al leer: el presupuesto es lo
    que se aprobó, y corregir el costo del catálogo en marzo no cambia lo que se
    aprobó en enero.
    """

    __tablename__ = "project_budget_lines"
    __table_args__ = (Index("ix_project_budget_lines_org_budget", "organization_id", "budget_id"),)

    budget_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_budgets.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(30), nullable=False, default="materials")
    item_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouse_items.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="unit")
    unit_cost: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(MONEY, nullable=False, default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    budget: Mapped["ProjectBudget"] = relationship("ProjectBudget", back_populates="lines", lazy="raise")


class ProjectDayLog(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """La jornada del punto 4: un día de trabajo de una obra.

    Los trabajos fuera de rebate duran varios días y no siempre con el mismo
    técnico, así que el técnico vive **en la jornada** y no en el proyecto: la
    misma obra tiene una jornada distinta cada día, con gente distinta. Que una
    obra tenga más de una jornada es justo lo que la vuelve «de varios días»,
    que es lo que la Agenda marca.

    Los gastos del día no se capturan acá: se **leen** de `expenses` por fecha,
    porque ya están cargados y volver a escribirlos sería contarlos dos veces.
    """

    __tablename__ = "project_day_logs"
    __table_args__ = (
        # Una línea por día: el diario se lee como una jornada por renglón.
        UniqueConstraint("organization_id", "project_id", "log_date", name="uq_project_day_log_date"),
        Index("ix_project_day_logs_org_project", "organization_id", "project_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id"), nullable=False, index=True)
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
    # El técnico del día, que no tiene por qué ser el asignado al proyecto.
    technician_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    # Con quién más estuvo. Texto libre: la cuadrilla no siempre son usuarios.
    crew: Mapped[str | None] = mapped_column(String(255))
    hours: Mapped[Decimal | None] = mapped_column(QUANTITY)
    work_done: Mapped[str | None] = mapped_column(Text)
    # Hasta dónde se avanzó, en una línea: es lo que se lee de un vistazo.
    progress_note: Mapped[str | None] = mapped_column(String(255))
    missing_materials: Mapped[str | None] = mapped_column(Text)
    next_day_plan: Mapped[str | None] = mapped_column(Text)
    incidents: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))

    materials: Mapped[list["ProjectDayLogMaterial"]] = relationship(
        "ProjectDayLogMaterial", back_populates="day_log", lazy="raise")


class ProjectDayLogMaterial(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """El material que se usó ese día.

    Cuando la línea apunta a un artículo del catálogo y dice de qué camioneta
    salió, registrar la jornada **descuenta la existencia**: ese material se usó
    y ya no está en la camioneta. Si es algo que se compró directo a la obra,
    la línea va sin artículo ni ubicación y queda solo como anotación del día.
    """

    __tablename__ = "project_day_log_materials"
    __table_args__ = (Index("ix_project_day_log_materials_org_log", "organization_id", "day_log_id"),)

    day_log_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("project_day_logs.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouse_items.id"), index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(QUANTITY, nullable=False, default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="unit")
    # De dónde salió (la camioneta). Nulo = la línea no movió existencia.
    location_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouse_locations.id"))
    # El movimiento que la descontó, para poder seguirle la pista.
    movement_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("warehouse_movements.id"))
    notes: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    day_log: Mapped["ProjectDayLog"] = relationship("ProjectDayLog", back_populates="materials", lazy="raise")
