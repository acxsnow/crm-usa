"""align org-scoped models with organization foreign keys

Revision ID: 0040
Revises: 0039
Create Date: 2026-10-25
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ORG_SCOPED_TABLES = [
    "roles",
    "audit_events",
    "users",
    "invitations",
    "customers",
    "data_consents",
    "funder_statuses",
    "activities",
    "programs",
    "program_versions",
    "program_zones",
    "cases",
    "case_stage_events",
    "case_step_submissions",
    "case_files",
    "case_terms_acceptances",
    "projects",
    "project_technician_assignments",
    "checklist_templates",
    "tasks",
    "evidence",
    "attestations",
    "permits",
    "inspections",
    "installed_equipment",
    "project_materials",
    "project_reviews",
    "attendance_settings",
    "work_shifts",
    "time_entries",
    "time_entry_pauses",
    "attendance_events",
    "novelty_reasons",
    "attendance_novelties",
    "time_entry_corrections",
    "payroll_periods",
    "payroll_period_events",
    "warehouse_locations",
    "warehouse_categories",
    "warehouse_items",
    "warehouse_stock",
    "warehouse_movements",
    "warehouse_release_orders",
    "warehouse_release_lines",
    "warehouse_kit_templates",
    "warehouse_kit_items",
    "project_budgets",
    "project_budget_lines",
    "project_day_logs",
    "project_day_log_helpers",
    "project_day_log_materials",
    "cost_templates",
    "project_cost_entries",
    "project_extra_charges",
    "invoices",
    "document_sequences",
    "billing_program_profiles",
    "program_rebate_rates",
    "program_jurisdictions",
    "program_claim_requirements",
    "rebate_claims",
    "rebate_claim_attempts",
    "rebate_claim_checks",
    "quotes",
    "notifications",
    "notification_deliveries",
    "notification_templates",
    "notification_preferences",
    "notification_settings",
    "products",
    "marketing_consents",
    "campaigns",
    "campaign_recipients",
    "email_marketing_consents",
    "marketing_contacts",
    "expenses",
    "suppliers",
    "supplier_documents",
    "supplier_invoices",
    "supplier_invoice_approvals",
    "supplier_payments",
    "finance_settings",
    "bank_statements",
    "bank_statement_lines",
    "field_definitions",
    "program_terms",
    "workflow_phases",
    "workflow_steps",
    "workflow_step_fields",
    "zone_assignments",
]


def _constraint_name(table_name: str) -> str:
    return f"fk_{table_name}_organization_id_organizations"


def _has_org_fk(inspector: sa.Inspector, table_name: str) -> bool:
    for fk in inspector.get_foreign_keys(table_name):
        if fk.get("referred_table") != "organizations":
            continue
        if fk.get("constrained_columns") == ["organization_id"]:
            return True
    return False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table_name in ORG_SCOPED_TABLES:
        if table_name not in existing_tables or _has_org_fk(inspector, table_name):
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.create_foreign_key(
                _constraint_name(table_name),
                "organizations",
                ["organization_id"],
                ["id"],
                ondelete="CASCADE",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    for table_name in ORG_SCOPED_TABLES:
        if table_name not in existing_tables:
            continue
        wanted = _constraint_name(table_name)
        names = {fk.get("name") for fk in inspector.get_foreign_keys(table_name)}
        if wanted not in names:
            continue
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.drop_constraint(wanted, type_="foreignkey")
