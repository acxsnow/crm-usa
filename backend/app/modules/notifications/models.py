"""Notificaciones (módulo 7, spec `2026-10-07-modulo-7-notificaciones-design.md`).

- `Notification`: el aviso en la app de una persona. Siempre se crea.
- `NotificationDelivery`: cada envío por correo o SMS de ese aviso, con su
  estado e intentos. Es la cola: el worker toma las pendientes.
- `NotificationTemplate`: el texto que la organización cambió para un evento
  y canal. Sin fila, se usa el texto por defecto del código.
- `NotificationPreference`: si la persona quiere también correo o SMS.
- `NotificationSettings`: ajustes de la organización (umbral de días en
  aprobación, SMS al cliente apagado).
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID

CHANNELS = ("in_app", "email", "sms")
DELIVERY_STATUSES = ("pending", "sent", "failed", "skipped")
MAX_ATTEMPTS = 5


class Notification(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at"),
        # Las alertas diarias no se repiten: una por persona y clave.
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_dedupe"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500))
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    dedupe_key: Mapped[str | None] = mapped_column(String(200))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationDelivery(UUIDPKMixin, OrgScopedMixin, Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (Index("ix_notification_deliveries_queue", "status", "next_attempt_at"),)

    notification_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    to: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NotificationTemplate(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "notification_templates"
    __table_args__ = (UniqueConstraint("organization_id", "event", "channel", name="uq_notification_template"),)

    event: Mapped[str] = mapped_column(String(60), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationPreference(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_preference_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sms_phone: Mapped[str | None] = mapped_column(String(30))


class NotificationSettings(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "notification_settings"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_notification_settings_org"),)

    approval_alert_business_days: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    permit_expiry_alert_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    # SMS al cliente final: apagado hasta registrar su consentimiento.
    customer_sms_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
