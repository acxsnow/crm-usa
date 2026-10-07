"""Notificaciones (módulo 7): avisos en la app, cola de envíos por correo y
SMS, plantillas por organización, preferencias por persona y ajustes.

Revision ID: 0020
Revises: 0019
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def _org():
    return sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                     nullable=False, index=True)


def _stamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(500)),
        sa.Column("entity_type", sa.String(40)),
        sa.Column("entity_id", sa.String(64)),
        sa.Column("dedupe_key", sa.String(200)),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_dedupe"),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"])
    op.create_table(
        "notification_deliveries",
        sa.Column("id", GUID(), primary_key=True), _org(),
        sa.Column("notification_id", GUID(), sa.ForeignKey("notifications.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("to", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500)),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_notification_deliveries_queue", "notification_deliveries", ["status", "next_attempt_at"])
    op.create_table(
        "notification_templates",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("event", sa.String(60), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.UniqueConstraint("organization_id", "event", "channel", name="uq_notification_template"),
    )
    op.create_table(
        "notification_preferences",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("user_id", GUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_phone", sa.String(30)),
        sa.UniqueConstraint("user_id", name="uq_notification_preference_user"),
    )
    op.create_table(
        "notification_settings",
        sa.Column("id", GUID(), primary_key=True), _org(), *_stamps(),
        sa.Column("approval_alert_business_days", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("permit_expiry_alert_days", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("customer_sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("organization_id", name="uq_notification_settings_org"),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
    op.drop_table("notification_preferences")
    op.drop_table("notification_templates")
    op.drop_index("ix_notification_deliveries_queue", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("ix_notifications_user_unread", table_name="notifications")
    op.drop_table("notifications")
