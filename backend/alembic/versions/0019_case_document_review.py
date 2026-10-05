"""Revisión de documentos del expediente (módulo 3).

Cada archivo del expediente lleva su estado de revisión (pendiente, aceptado
o rechazado), la nota de quien lo revisó y, para los documentos adicionales
que no salen de un campo del formulario, su nombre.

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("case_files", sa.Column("label", sa.String(length=255), nullable=True))
    op.add_column("case_files", sa.Column("review_status", sa.String(length=20), nullable=False,
                                          server_default="pending"))
    op.add_column("case_files", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column("case_files", sa.Column("reviewed_by_user_id", app.db.types.GUID(), nullable=True))
    op.add_column("case_files", sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_case_files_review_status", "case_files", ["organization_id", "review_status"])


def downgrade() -> None:
    op.drop_index("ix_case_files_review_status", table_name="case_files")
    for col in ("reviewed_at", "reviewed_by_user_id", "review_notes", "review_status", "label"):
        op.drop_column("case_files", col)
