"""Módulo 6: facturación y cobro.

Spec: docs/superpowers/specs/2026-09-28-modulo-6-cobro-design.md

Se construye por fases del plan; cada fase agrega su bloque aquí mientras la
migración no haya llegado a main.

Fase 1 — base:
- `invoices`: tipo (rebate/particular), expediente, factura que reemplaza,
  estado de DOCUMENTO (borrador/emitida/anulada) y motivo de anulación;
  `project_id` pasa a opcional (trabajo particular sin instalación). El estado
  de pago deja de guardarse: se calcula de los pagos. El enum `invoice_status`
  se reemplaza: pending/sent/overdue/paid → issued; cancelled → void.
- `invoice_lines` y `document_sequences` (numeración por serie y año).

Fase 2 — configuración por programa:
- `billing_program_profiles`, `program_rebate_rates`, `program_jurisdictions`,
  `program_claim_requirements`.
- Permisos `billing.configure` y `quotes.manage`, asignados a los roles y al
  módulo "Facturación y cobros" en las bases existentes.

Fase 3 — ajuste del módulo 5:
- `project_reviews`: confirmaciones y devoluciones del acta.
- `rebate_claims`, `rebate_claim_attempts`, `rebate_claim_checks` e
  `invoices.claim_id`: el cobro de rebate (fase 4).
- `quotes`, `quote_lines` e `invoices.quote_id`: trabajo particular (fase 6).

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

import app.db.types

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_STATUSES = ("pending", "sent", "paid", "overdue", "cancelled")


def upgrade() -> None:
    # --- invoices -----------------------------------------------------------
    op.add_column("invoices", sa.Column("kind", sa.String(20), nullable=False, server_default="particular"))
    op.add_column("invoices", sa.Column("case_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key("invoices_case_id_fkey", "invoices", "cases", ["case_id"], ["id"])
    op.create_index(op.f("ix_invoices_case_id"), "invoices", ["case_id"])
    op.add_column("invoices", sa.Column("replaces_invoice_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key("invoices_replaces_invoice_id_fkey", "invoices", "invoices", ["replaces_invoice_id"], ["id"])
    op.add_column("invoices", sa.Column("document_status", sa.String(10), nullable=False, server_default="issued"))
    op.add_column("invoices", sa.Column("void_reason", sa.Text(), nullable=True))
    op.execute("UPDATE invoices SET document_status = CASE WHEN status::text = 'cancelled' THEN 'void' ELSE 'issued' END")
    op.drop_column("invoices", "status")
    sa.Enum(name="invoice_status").drop(op.get_bind(), checkfirst=True)
    op.alter_column("invoices", "project_id", existing_type=app.db.types.GUID(), nullable=True)

    op.create_table(
        "invoice_lines",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("invoice_id", app.db.types.GUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(20), nullable=False, server_default="service"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("service_code", sa.String(50), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoice_lines_invoice_id"), "invoice_lines", ["invoice_id"])

    op.create_table(
        "document_sequences",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("series", sa.String(10), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "series", "year", name="uq_document_sequence"),
    )
    op.create_index(op.f("ix_document_sequences_organization_id"), "document_sequences", ["organization_id"])

    _upgrade_phase2()
    _upgrade_phase3()
    _upgrade_phase4()
    _upgrade_phase6()


def downgrade() -> None:
    _downgrade_phase6()
    _downgrade_phase4()
    _downgrade_phase3()
    _downgrade_phase2()
    op.drop_table("document_sequences")
    op.drop_table("invoice_lines")

    # Vuelve el enum anterior. El estado de pago no existía como dato aparte:
    # anuladas → cancelled; el resto → pending (el estado real sale de los pagos).
    status = sa.Enum(*_OLD_STATUSES, name="invoice_status")
    status.create(op.get_bind(), checkfirst=True)
    op.add_column("invoices", sa.Column("status", status, nullable=False, server_default="pending"))
    op.execute("UPDATE invoices SET status = CASE WHEN document_status = 'void' THEN 'cancelled'::invoice_status "
               "ELSE 'pending'::invoice_status END")
    # Las facturas sin proyecto (trabajo particular) no caben en el esquema
    # anterior, que exigía proyecto.
    op.execute("DELETE FROM invoices WHERE project_id IS NULL")
    op.alter_column("invoices", "project_id", existing_type=app.db.types.GUID(), nullable=False)
    op.drop_column("invoices", "void_reason")
    op.drop_column("invoices", "document_status")
    op.drop_constraint("invoices_replaces_invoice_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "replaces_invoice_id")
    op.drop_index(op.f("ix_invoices_case_id"), table_name="invoices")
    op.drop_constraint("invoices_case_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "case_id")
    op.drop_column("invoices", "kind")


# ---------------------------------------------------------------------------
# Fase 2 — configuración de cobro por programa y permisos nuevos
# ---------------------------------------------------------------------------

_NEW_PERMISSIONS = {
    "billing.configure": "Configurar el cobro de los programas (tarifas, jurisdicciones y requisitos)",
    "quotes.manage": "Gestionar cotizaciones de trabajo particular",
}
# Rol → permisos nuevos (mismo reparto que DEFAULT_ROLE_PERMISSIONS). Se
# aplica a los roles del sistema y a las copias de cada organización.
_ROLE_GRANTS = {
    "organization_admin": ["billing.configure", "quotes.manage"],
    "accounting": ["billing.configure", "quotes.manage"],
    "admin_staff": ["quotes.manage"],
}


def _upgrade_phase2() -> None:
    def org_project_columns():
        return [
            sa.Column("id", app.db.types.GUID(), nullable=False),
            sa.Column("organization_id", app.db.types.GUID(), nullable=False),
            sa.Column("program_id", app.db.types.GUID(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        ]

    def finish(table):
        op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
        op.create_index(op.f(f"ix_{table}_program_id"), table, ["program_id"])

    program_fk = sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE")

    op.create_table(
        "billing_program_profiles", *org_project_columns(),
        sa.Column("issuer_name", sa.String(255)), sa.Column("issuer_address", sa.String(500)),
        sa.Column("issuer_phone", sa.String(50)), sa.Column("issuer_email", sa.String(255)),
        sa.Column("legal_text", sa.Text()),
        sa.Column("expected_payment_days", sa.Integer(), nullable=False, server_default="45"),
        program_fk, sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "program_id", name="uq_billing_profile_program"),
    )
    finish("billing_program_profiles")
    op.create_table(
        "program_rebate_rates", *org_project_columns(),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False), sa.Column("valid_to", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    finish("program_rebate_rates")
    op.create_table(
        "program_jurisdictions", *org_project_columns(),
        sa.Column("kind", sa.String(10), nullable=False), sa.Column("value", sa.String(120), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False), sa.Column("valid_to", sa.Date()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
    )
    finish("program_jurisdictions")
    op.create_index(op.f("ix_program_jurisdictions_value"), "program_jurisdictions", ["value"])
    op.create_table(
        "program_claim_requirements", *org_project_columns(),
        sa.Column("code", sa.String(50), nullable=False), sa.Column("label", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"), sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("program_id", "code", name="uq_program_requirement_code"),
    )
    finish("program_claim_requirements")

    # Permisos nuevos: catálogo, roles y módulo "billing". Todo en SQL puro
    # (sin leer filas desde Python) para que la migración también se pueda
    # generar en modo offline (--sql).
    for code, description in _NEW_PERMISSIONS.items():
        op.execute(sa.text(
            "INSERT INTO permissions (id, code, description) SELECT gen_random_uuid(), :code, :description "
            "WHERE NOT EXISTS (SELECT 1 FROM permissions WHERE code = :code)"
        ).bindparams(code=code, description=description))
    for role_code, codes in _ROLE_GRANTS.items():
        for code in codes:
            op.execute(sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "SELECT r.id, p.id FROM roles r, permissions p WHERE r.code = :role AND p.code = :perm "
                "AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id AND rp.permission_id = p.id)"
            ).bindparams(role=role_code, perm=code))
    for code in _NEW_PERMISSIONS:
        op.execute(sa.text(
            "INSERT INTO permission_module_items (id, module_id, permission_id, sort_order) "
            "SELECT gen_random_uuid(), m.id, p.id, 100 FROM permission_modules m, permissions p "
            "WHERE m.key = 'billing' AND p.code = :perm "
            "AND NOT EXISTS (SELECT 1 FROM permission_module_items i WHERE i.module_id = m.id AND i.permission_id = p.id)"
        ).bindparams(perm=code))


def _downgrade_phase2() -> None:
    for code in _NEW_PERMISSIONS:
        # role_permissions y permission_module_items caen en cascada.
        op.execute(sa.text("DELETE FROM permissions WHERE code = :code").bindparams(code=code))
    for table in ("program_claim_requirements", "program_jurisdictions", "program_rebate_rates",
                  "billing_program_profiles"):
        op.drop_table(table)


# ---------------------------------------------------------------------------
# Fase 3 — revisión administrativa del acta
# ---------------------------------------------------------------------------

def _upgrade_phase3() -> None:
    op.create_table(
        "project_reviews",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("project_id", app.db.types.GUID(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("actor_user_id", app.db.types.GUID()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_reviews_organization_id"), "project_reviews", ["organization_id"])
    op.create_index(op.f("ix_project_reviews_project_id"), "project_reviews", ["project_id"])


def _downgrade_phase3() -> None:
    op.drop_table("project_reviews")


# ---------------------------------------------------------------------------
# Fase 4 — cobro de rebate
# ---------------------------------------------------------------------------

def _org_columns():
    return [
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("organization_id", app.db.types.GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def _upgrade_phase4() -> None:
    op.create_table(
        "rebate_claims",
        *_org_columns(),
        sa.Column("project_id", app.db.types.GUID(), nullable=False),
        sa.Column("case_id", app.db.types.GUID()),
        sa.Column("program_id", app.db.types.GUID(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="preparing"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("rate_id", app.db.types.GUID()),
        sa.Column("installation_date", sa.Date(), nullable=False),
        sa.Column("applies", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("jurisdiction_label", sa.String(120)),
        sa.Column("override_reason", sa.Text()),
        sa.Column("paid_on", sa.Date()),
        sa.Column("paid_amount", sa.Numeric(12, 2)),
        sa.Column("payment_reference", sa.String(255)),
        sa.Column("withdrawn_reason", sa.Text()),
        sa.Column("created_by_user_id", app.db.types.GUID()),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"]),
        sa.ForeignKeyConstraint(["rate_id"], ["program_rebate_rates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for col in ("organization_id", "project_id", "case_id", "program_id", "status"):
        op.create_index(op.f(f"ix_rebate_claims_{col}"), "rebate_claims", [col])
    op.create_index("uq_rebate_claim_active", "rebate_claims", ["project_id", "program_id"], unique=True,
                    postgresql_where=sa.text("status <> 'withdrawn'"))

    op.create_table(
        "rebate_claim_attempts",
        *_org_columns(),
        sa.Column("claim_id", app.db.types.GUID(), nullable=False),
        sa.Column("submitted_on", sa.Date(), nullable=False),
        sa.Column("portal_reference", sa.String(255)),
        sa.Column("submitted_by_user_id", app.db.types.GUID()),
        sa.Column("result", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("rejection_category", sa.String(20)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("resolved_on", sa.Date()),
        sa.Column("resolved_by_user_id", app.db.types.GUID()),
        sa.ForeignKeyConstraint(["claim_id"], ["rebate_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_rebate_claim_attempts_organization_id"), "rebate_claim_attempts", ["organization_id"])
    op.create_index(op.f("ix_rebate_claim_attempts_claim_id"), "rebate_claim_attempts", ["claim_id"])

    op.create_table(
        "rebate_claim_checks",
        *_org_columns(),
        sa.Column("claim_id", app.db.types.GUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("confirmed_by_user_id", app.db.types.GUID()),
        sa.ForeignKeyConstraint(["claim_id"], ["rebate_claims.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("claim_id", "code", name="uq_rebate_claim_check"),
    )
    op.create_index(op.f("ix_rebate_claim_checks_organization_id"), "rebate_claim_checks", ["organization_id"])
    op.create_index(op.f("ix_rebate_claim_checks_claim_id"), "rebate_claim_checks", ["claim_id"])

    op.add_column("invoices", sa.Column("claim_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key("invoices_claim_id_fkey", "invoices", "rebate_claims", ["claim_id"], ["id"])
    op.create_index(op.f("ix_invoices_claim_id"), "invoices", ["claim_id"])


def _downgrade_phase4() -> None:
    op.drop_index(op.f("ix_invoices_claim_id"), table_name="invoices")
    op.drop_constraint("invoices_claim_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "claim_id")
    op.drop_table("rebate_claim_checks")
    op.drop_table("rebate_claim_attempts")
    op.drop_table("rebate_claims")


# ---------------------------------------------------------------------------
# Fase 6 — trabajo particular: cotizaciones con versiones
# ---------------------------------------------------------------------------

def _upgrade_phase6() -> None:
    op.create_table(
        "quotes",
        *_org_columns(),
        sa.Column("customer_id", app.db.types.GUID(), nullable=False),
        sa.Column("project_id", app.db.types.GUID()),
        sa.Column("quote_number", sa.String(50), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("previous_version_id", app.db.types.GUID()),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("title", sa.String(255)),
        sa.Column("valid_until", sa.Date()),
        sa.Column("notes", sa.Text()),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("rejection_reason", sa.Text()),
        sa.Column("created_by_user_id", app.db.types.GUID()),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["previous_version_id"], ["quotes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "quote_number", "version", name="uq_quote_version"),
    )
    for col in ("organization_id", "customer_id", "project_id", "quote_number", "status"):
        op.create_index(op.f(f"ix_quotes_{col}"), "quotes", [col])

    op.create_table(
        "quote_lines",
        sa.Column("id", app.db.types.GUID(), nullable=False),
        sa.Column("quote_id", app.db.types.GUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(20), nullable=False, server_default="service"),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("service_code", sa.String(50)),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_quote_lines_quote_id"), "quote_lines", ["quote_id"])

    op.add_column("invoices", sa.Column("quote_id", app.db.types.GUID(), nullable=True))
    op.create_foreign_key("invoices_quote_id_fkey", "invoices", "quotes", ["quote_id"], ["id"])
    op.create_index(op.f("ix_invoices_quote_id"), "invoices", ["quote_id"])


def _downgrade_phase6() -> None:
    op.drop_index(op.f("ix_invoices_quote_id"), table_name="invoices")
    op.drop_constraint("invoices_quote_id_fkey", "invoices", type_="foreignkey")
    op.drop_column("invoices", "quote_id")
    op.drop_table("quote_lines")
    op.drop_table("quotes")
