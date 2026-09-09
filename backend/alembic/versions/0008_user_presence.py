"""Add users.last_seen_at and users.is_available for the technician monitor

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("users", "is_available")
    op.drop_column("users", "last_seen_at")
