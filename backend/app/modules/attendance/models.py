"""Turnos, asistencia y ubicación del personal (spec
`docs/superpowers/specs/2026-10-24-turnos-mapa-design.md`).

Tres ideas sostienen el módulo:

- **La malla no es la marcación.** `work_shifts` dice qué se esperaba;
  `time_entries` dice qué pasó. El panel compara las dos y nunca deduce una
  marca de la otra.
- **Turno activo, ubicación disponible y cumplimiento verificado son tres
  cosas distintas.** Una persona puede estar trabajando sin señal: perder el
  celular no cierra el turno ni resta horas. La ubicación vive solo en
  `attendance_events` y lo único que dice es dónde estaba el teléfono cuando
  marcó.
- **Nada se reescribe.** La bitácora de eventos solo crece; una corrección
  guarda el valor original en `time_entry_corrections` antes de cambiar la
  marcación, y un período cerrado no se toca sin reabrirlo con motivo.

Todas las horas se guardan en UTC. El «día» del turno es el día local de la
organización (`organizations.timezone`, `field_ops/clock.py`).
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class AttendanceSettings(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Las reglas de cada organización. Los valores por defecto son los del
    spec mientras Don Aldo no diga otra cosa: todo se cambia aquí, sin código."""

    __tablename__ = "attendance_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_attendance_settings_org"),)

    late_tolerance_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    early_leave_tolerance_minutes: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    # Extras desde la hora 8 del día y la 40 de la semana (regla de California).
    # 0 apaga el umbral.
    daily_overtime_after_minutes: Mapped[int] = mapped_column(Integer, default=480, nullable=False)
    weekly_overtime_after_minutes: Mapped[int] = mapped_column(Integer, default=2400, nullable=False)
    # Seguimiento con la app abierta cada N minutos (alternativa B). 0 = solo eventos.
    tracking_interval_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    location_retention_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    # Bloquear el trabajo de campo (evidencias, checklist, diario…) hasta marcar.
    require_clock_in_for_field_work: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # ¿La pausa se paga? Por defecto no: resta de las horas efectivas.
    paid_pauses: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class WorkShift(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Un turno de la malla: lo que se esperaba de una persona un día."""

    __tablename__ = "work_shifts"
    __table_args__ = (Index("ix_work_shifts_org_date", "organization_id", "shift_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    # El día local en que empieza (un turno nocturno termina al día siguiente).
    shift_date: Mapped[date] = mapped_column(Date, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    notes: Mapped[str | None] = mapped_column(String(255))
    # scheduled | cancelled
    status: Mapped[str] = mapped_column(String(20), default="scheduled", nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))


class TimeEntry(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """La marcación real de una jornada: de INICIAR a FINALIZAR TURNO."""

    __tablename__ = "time_entries"
    __table_args__ = (
        # Una sola marcación abierta por persona, aunque marque desde dos
        # teléfonos a la vez.
        Index("uq_time_entries_one_open", "organization_id", "user_id", unique=True,
              postgresql_where=text("status = 'open'"), sqlite_where=text("status = 'open'")),
        Index("ix_time_entries_org_date", "organization_id", "work_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("work_shifts.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    # La hora que cuenta. En línea es la del servidor; sin señal, la del
    # teléfono (dentro de la ventana aceptada) y queda marcada `offline`.
    clock_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_in_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    clock_in_device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_in_offline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out_device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    clock_out_offline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # open | closed | approved
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    # self | admin (regularizada por Administración)
    closed_by: Mapped[str | None] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text)
    approved_minutes: Mapped[int | None] = mapped_column(Integer)
    approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pauses: Mapped[list["TimeEntryPause"]] = relationship(
        "TimeEntryPause", lazy="selectin", order_by="TimeEntryPause.started_at", cascade="all, delete-orphan")


class TimeEntryPause(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "time_entry_pauses"

    time_entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("time_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(String(120))


class AttendanceEvent(UUIDPKMixin, OrgScopedMixin, Base):
    """La bitácora: cada cosa que pasó, con la hora del teléfono y la de
    llegada al servidor. Solo se agrega; la retención borra las coordenadas
    y deja el evento."""

    __tablename__ = "attendance_events"
    __table_args__ = (
        # Un reintento con el mismo id del teléfono no duplica.
        UniqueConstraint("organization_id", "user_id", "client_event_id", name="uq_attendance_event_client"),
        Index("ix_attendance_events_org_user_time", "organization_id", "user_id", "received_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    time_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("time_entries.id", ondelete="SET NULL"), index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(30), nullable=False)
    client_event_id: Mapped[str | None] = mapped_column(String(64))
    device_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # La hora que cuenta para el evento (servidor, o teléfono si llegó sin señal).
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    offline: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    accuracy_m: Mapped[float | None] = mapped_column(Float)
    # ok | denied | unavailable | timeout | not_requested | purged
    location_status: Mapped[str] = mapped_column(String(20), default="not_requested", nullable=False)
    # Kilómetros desde el evento con ubicación anterior del mismo turno.
    distance_km: Mapped[float | None] = mapped_column(Float)
    # straight_line | route
    distance_source: Mapped[str | None] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(255))
    # El resultado devuelto la primera vez, para responder igual a un reintento.
    result: Mapped[dict | None] = mapped_column(JSON)


class NoveltyReason(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Catálogo administrable de motivos de novedad."""

    __tablename__ = "novelty_reasons"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_novelty_reason_code"),)

    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class AttendanceNovelty(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """Lo que el empleado declara (llegó tarde por X, olvidó marcar) o pide
    corregir. Es una explicación declarada, distinta de un hecho técnico."""

    __tablename__ = "attendance_novelties"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    time_entry_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("time_entries.id"), index=True)
    shift_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("work_shifts.id"), index=True)
    # late_arrival | early_departure | missed_clock_in | missed_clock_out |
    # correction | absence | connectivity | other
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    reason_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("novelty_reasons.id"))
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    requested_clock_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requested_clock_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # pending | approved | rejected
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    reviewed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_note: Mapped[str | None] = mapped_column(Text)


class TimeEntryCorrection(UUIDPKMixin, OrgScopedMixin, Base):
    """Cada cambio a una marcación: qué tenía, qué quedó, quién y por qué."""

    __tablename__ = "time_entry_corrections"

    time_entry_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("time_entries.id", ondelete="CASCADE"), nullable=False, index=True)
    novelty_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("attendance_novelties.id"))
    corrected_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    corrected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    before_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    after_data: Mapped[dict] = mapped_column(JSON, nullable=False)


class PayrollPeriod(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "payroll_periods"
    __table_args__ = (UniqueConstraint("organization_id", "start_date", "end_date", name="uq_payroll_period"),)

    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    # open | closed
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    closed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id"))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PayrollPeriodEvent(UUIDPKMixin, OrgScopedMixin, Base):
    """Historial del período: cada cierre y cada reapertura con su motivo."""

    __tablename__ = "payroll_period_events"

    period_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("payroll_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    # created | closed | reopened
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id"), nullable=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
