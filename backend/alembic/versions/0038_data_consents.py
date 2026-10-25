"""Autorización de tratamiento de datos personales (aviso al momento de la captura).

Antes se guardaban nombre, teléfono, correo y dirección del cliente sin dejar
constancia de que el cliente hubiera autorizado su tratamiento. Esta migración
crea `data_consents`: una fila por cada autorización, con el texto del aviso
—versionado— que el cliente vio, lo que se estaba capturando, y la evidencia de
dónde y desde qué equipo se otorgó. Es inmutable, como
`case_terms_acceptances` (0017).

Revision ID: 0038
Revises: 0037
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0038"
down_revision: Union[str, None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = app.db.types.GUID


def upgrade() -> None:
    op.create_table(
        "data_consents",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("customer_id", GUID()),
        sa.Column("case_id", GUID()),
        sa.Column("customer_name", sa.String(255)),
        sa.Column("contact_snapshot", sa.JSON()),
        sa.Column("document_version", sa.String(30), nullable=False),
        sa.Column("document_language", sa.String(5), nullable=False, server_default="es"),
        sa.Column("document_text", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_by_user_id", GUID()),
        sa.Column("ip_address", sa.String(64)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_data_consents_organization_id"), "data_consents", ["organization_id"])
    op.create_index(op.f("ix_data_consents_customer_id"), "data_consents", ["customer_id"])
    op.create_index(op.f("ix_data_consents_case_id"), "data_consents", ["case_id"])


def downgrade() -> None:
    op.drop_table("data_consents")
