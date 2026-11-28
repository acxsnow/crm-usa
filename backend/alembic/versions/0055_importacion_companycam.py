"""Importación de CompanyCam: origen de expedientes, clientes, usuarios y
archivos; notas del expediente y cola de descarga (`import_items`).

Revision ID: 0055
Revises: 0054
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op
from app.db.types import GUID

revision: str = "0055"
down_revision: Union[str, None] = "0054"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tiempos():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    ]


def upgrade() -> None:
    op.add_column("cases", sa.Column("external_ref", sa.String(64)))
    op.create_unique_constraint("uq_case_org_source_ref", "cases", ["organization_id", "source", "external_ref"])

    op.add_column("case_stage_events",
                  sa.Column("imported", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.add_column("customers", sa.Column("source", sa.String(20), nullable=False, server_default="app"))
    op.add_column("customers", sa.Column("external_ref", sa.String(64)))
    op.create_unique_constraint("uq_customer_org_source_ref", "customers",
                                ["organization_id", "source", "external_ref"])

    op.add_column("users", sa.Column("source", sa.String(20), nullable=False, server_default="app"))
    op.add_column("users", sa.Column("external_ref", sa.String(64)))
    op.create_unique_constraint("uq_user_org_source_ref", "users", ["organization_id", "source", "external_ref"])

    op.add_column("case_files", sa.Column("external_ref", sa.String(64)))
    op.add_column("case_files", sa.Column("author_name", sa.String(255)))
    op.add_column("case_files", sa.Column("tags", sa.JSON()))

    op.create_table(
        "case_notes",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("case_id", GUID(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("author_name", sa.String(255)),
        sa.Column("author_user_id", GUID()),
        sa.Column("source", sa.String(20), nullable=False, server_default="companycam"),
        sa.Column("external_ref", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON()),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        *_tiempos(),
        sa.UniqueConstraint("case_id", "kind", "external_ref", name="uq_case_note_ref"),
    )

    op.create_table(
        "import_items",
        sa.Column("id", GUID(), primary_key=True),
        sa.Column("organization_id", GUID(), sa.ForeignKey("organizations.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="companycam"),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("case_id", GUID(), sa.ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("case_file_id", GUID(), sa.ForeignKey("case_files.id", ondelete="SET NULL")),
        sa.Column("remote_url", sa.Text()),
        sa.Column("payload", sa.JSON()),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text()),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("downloaded_at", sa.DateTime(timezone=True)),
        *_tiempos(),
        sa.UniqueConstraint("organization_id", "source", "kind", "external_id", name="uq_import_item_ref"),
    )
    op.create_index("ix_import_item_status_kind", "import_items", ["status", "kind"])


def downgrade() -> None:
    op.drop_index("ix_import_item_status_kind", table_name="import_items")
    op.drop_table("import_items")
    op.drop_table("case_notes")
    op.drop_column("case_files", "tags")
    op.drop_column("case_files", "author_name")
    op.drop_column("case_files", "external_ref")
    op.drop_constraint("uq_user_org_source_ref", "users", type_="unique")
    op.drop_column("users", "external_ref")
    op.drop_column("users", "source")
    op.drop_constraint("uq_customer_org_source_ref", "customers", type_="unique")
    op.drop_column("customers", "external_ref")
    op.drop_column("customers", "source")
    op.drop_column("case_stage_events", "imported")
    op.drop_constraint("uq_case_org_source_ref", "cases", type_="unique")
    op.drop_column("cases", "external_ref")
