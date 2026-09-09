import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Table, Column, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin, TimestampMixin, UUIDPKMixin
from app.db.types import GUID


class UserStatus(str, enum.Enum):
    invited = "invited"
    active = "active"
    inactive = "inactive"
    locked = "locked"


# Role <-> Permission (static catalog, many-to-many)
role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", GUID(), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", GUID(), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(UUIDPKMixin, Base):
    __tablename__ = "permissions"

    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(255))


class Role(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    """System default roles have organization_id = NULL; custom roles belong to an org (spec 5.3)."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "code", name="uq_role_org_code"),)

    # Overrides OrgScopedMixin's NOT NULL — matches alembic/versions/0001_initial.py,
    # where "roles.organization_id" is nullable=True for exactly this reason
    # (system-default rows carry NULL). The mixin default had drifted out of
    # sync with the migration, which only surfaced when tests build the
    # schema from these models via Base.metadata.create_all() instead of
    # running the migration.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), index=True)

    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    permissions: Mapped[list["Permission"]] = relationship(
        "Permission", secondary=role_permissions, lazy="selectin"
    )


class User(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("organization_id", "email", name="uq_user_org_email"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email_display: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.invited, nullable=False
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_platform_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Bumped on password reset (spec 6.3.7: revoke ALL sessions). Every JWT
    # carries the token_version it was issued under ("ver" claim); a token
    # whose version doesn't match the user's current value is rejected —
    # this works even without Redis, unlike a single-token denylist.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    roles: Mapped[list["UserRole"]] = relationship(
        "UserRole", back_populates="user", lazy="selectin", cascade="all, delete-orphan"
    )


class UserRole(UUIDPKMixin, Base):
    __tablename__ = "user_roles"
    __table_args__ = (UniqueConstraint("user_id", "role_id", name="uq_user_role"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("roles.id", ondelete="CASCADE"), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="roles")
    role: Mapped["Role"] = relationship("Role", lazy="selectin")


class Invitation(UUIDPKMixin, TimestampMixin, OrgScopedMixin, Base):
    __tablename__ = "invitations"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    invited_by_user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    role_ids: Mapped[str] = mapped_column(String(2000), nullable=False)  # comma-separated role UUIDs
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PasswordResetToken(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_ip: Mapped[str | None] = mapped_column(String(64))
