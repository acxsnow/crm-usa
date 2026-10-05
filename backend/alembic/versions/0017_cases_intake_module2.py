"""Módulo 2: lo que el vendedor captura en la puerta.

Spec `docs/superpowers/specs/2026-10-04-modulo-2-vendedor-design.md`.
Tablas nuevas: `case_step_submissions` (respuestas inmutables por paso y
visitas), `case_files` (fotos, documentos, videos del formulario) y
`case_terms_acceptances` (términos aceptados y firma del cliente).

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.create_table(
        "case_step_submissions",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("case_id", GUID(), nullable=False),
        sa.Column("version_id", GUID()),
        sa.Column("step_code", sa.String(50), nullable=False),
        sa.Column("answers", sa.JSON(), nullable=False),
        sa.Column("submitted_by_user_id", GUID()),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["version_id"], ["program_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_step_submissions_organization_id"), "case_step_submissions", ["organization_id"])
    op.create_index(op.f("ix_case_step_submissions_case_id"), "case_step_submissions", ["case_id"])
    op.create_index("ix_case_step_submission_case_step", "case_step_submissions",
                    ["case_id", "step_code", "submitted_at"])

    op.create_table(
        "case_files",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("case_id", GUID(), nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("watermarked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("uploaded_by_user_id", GUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_files_organization_id"), "case_files", ["organization_id"])
    op.create_index(op.f("ix_case_files_case_id"), "case_files", ["case_id"])

    op.create_table(
        "case_terms_acceptances",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("case_id", GUID(), nullable=False),
        sa.Column("terms_id", GUID()),
        sa.Column("terms_version", sa.String(30)),
        sa.Column("terms_language", sa.String(5)),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("signature_path", sa.String(500), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("salesperson_user_id", GUID()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["terms_id"], ["program_terms.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_case_terms_acceptances_organization_id"), "case_terms_acceptances", ["organization_id"])
    op.create_index(op.f("ix_case_terms_acceptances_case_id"), "case_terms_acceptances", ["case_id"])


def downgrade() -> None:
    op.drop_table("case_terms_acceptances")
    op.drop_table("case_files")
    op.drop_table("case_step_submissions")
