"""Retira el formulario del modelo anterior (módulo 2).

`applications`, `application_documents` y `program_form_fields` eran el
formulario de solicitud antes del expediente. Los reemplazan el formulario
versionado del módulo 1 y lo que captura el vendedor en el módulo 2
(`case_step_submissions`, `case_files`, `case_terms_acceptances`). Las tres
tablas estaban vacías al retirarlas (verificado el 4 de octubre de 2026).
El downgrade las recrea vacías, con la forma que tenían después de la 0013.

Revision ID: 0018
Revises: 0017
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.drop_table("application_documents")
    op.drop_table("applications")
    op.drop_table("program_form_fields")


def downgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", GUID(), sa.ForeignKey("customers.id", ondelete="SET NULL")),
        sa.Column("program_code", sa.String(100), nullable=False),
        sa.Column("form_version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("answers", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("terms_version", sa.String(50)),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("terms_accepted_at", sa.DateTime(timezone=True)),
        sa.Column("customer_signature_path", sa.String(500)),
        sa.Column("customer_signed_at", sa.DateTime(timezone=True)),
        sa.Column("salesperson_user_id", GUID()),
        sa.Column("salesperson_signed_at", sa.DateTime(timezone=True)),
        sa.Column("review_notes", sa.Text()),
        sa.Column("reviewed_by_user_id", GUID()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("submitted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_applications_organization_id", "applications", ["organization_id"])
    op.create_index("ix_applications_program_code", "applications", ["program_code"])
    op.create_index("ix_applications_status", "applications", ["status"])
    op.create_table(
        "program_form_fields",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("program_code", sa.String(100), nullable=False),
        sa.Column("form_version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("options", sa.JSON()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_program_form_fields_organization_id", "program_form_fields", ["organization_id"])
    op.create_index("ix_program_form_fields_program_code", "program_form_fields", ["program_code"])
    op.create_table(
        "application_documents",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("application_id", GUID(), sa.ForeignKey("applications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("mime_type", sa.String(100)),
        sa.Column("size_bytes", sa.Integer()),
        sa.Column("uploaded_by_user_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_application_documents_organization_id", "application_documents", ["organization_id"])
    op.create_index("ix_application_documents_application_id", "application_documents", ["application_id"])
