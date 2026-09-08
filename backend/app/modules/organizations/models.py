import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class Organization(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(1024))
    primary_address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD", nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255))
    contact_phone: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class PlanLimit(UUIDPKMixin, TimestampMixin, Base):
    """Editable only by platform_super_admin; visible to org admins (spec 7.1)."""

    __tablename__ = "plan_limits"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), nullable=False, unique=True, index=True
    )
    max_active_users: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_storage_gb: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
